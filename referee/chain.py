"""Reference tamper-evident record: SHA-256 prev-hash chain + Merkle root + offline verify.

Generic primitives only (AGPL-safe). At the event this seam swaps to the production
Ed25519-signed ledger via the same append/verify interface (retained IP, via wheels).

Trust model (honest):
  - prev-hash chain + Merkle root  -> tamper-EVIDENT against corruption / silent edits.
  - per-leaf Ed25519 signature      -> tamper-EVIDENT against an *adversary* who can rewrite
                                       the file but does NOT hold the dedicated record key.
                                       (A DoD primitive, not just a prev-hash.)
  - per-leaf in-toto/DSSE attestation-> the EXTERNAL artifact is a RECOGNIZED standard, not a
                                       bespoke prev-hash. Each sealed leaf is ALSO emitted as an
                                       in-toto Statement v1 (subject = model-version-hash or
                                       decision id; predicate = the sealed payload) wrapped in a
                                       DSSE envelope, Ed25519-signed with the same record key.
                                       This is the INTEGRATION_SPEC §4 record reframe: SLSA/
                                       in-toto/Sigstore is what a DoD supply chain + an AO
                                       already recognize; we extend it to RUNTIME decisions
                                       onboard. The Merkle hash-chain stays as the INTERNAL
                                       mechanism; the attestation is the external face.
  - optional cosign blob signature  -> the same DoD-standard Sigstore tool already used for
                                       Zarf packaging, applied to the chain head.
  - optional one Rekor entry        -> public transparency on a connected host (offline-safe:
                                       absence never fails verification).

Concurrency model (honest): write() is atomic (temp file + os.replace) and serialized with an
exclusive flock; verify_dir() takes a shared flock. A reader (the CIC UI polls /api/state every
~4s) therefore can NEVER observe a half-written file or a chain/bundle pair caught mid-update,
so it cannot flash a spurious red tamper SNAP during the live demo. The attestations file is
written under the SAME exclusive lock, before chain.jsonl, so the cross-file pair stays
consistent for a shared-lock reader too.

Tamper-EVIDENT (+ cryptographically signed + emitted as standard in-toto/DSSE attestations),
not tamper-proof.

External artifact (the moat reframe, INTEGRATION_SPEC §4):
  attestations.jsonl  -> one DSSE-wrapped in-toto Statement v1 per leaf (the recognized format)
  bundle.json         -> chain head + merkle root + signing block (Ed25519 + optional cosign)
  chain.jsonl         -> the internal Merkle prev-hash chain (the implementation mechanism)
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

# fcntl is POSIX-only; degrade gracefully (no lock) on platforms without it (e.g. Windows CI).
try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore

GENESIS = "0" * 64

# Dedicated record-signing key (Ed25519). PRIVATE key is gitignored and never committed.
# The PUBLIC key may be committed so any offline verifier can check signatures without us.
_KEY_DIR = Path(__file__).resolve().parent / "keys"
_PRIV_PATH = _KEY_DIR / "record_ed25519.key"   # gitignored
_PUB_PATH = _KEY_DIR / "record_ed25519.pub"    # safe to commit

# ---- in-toto / DSSE / SLSA attestation constants (the EXTERNAL recognized format) ----
# in-toto Statement v1 (https://github.com/in-toto/attestation spec/v1/statement.md).
_INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
# DSSE payloadType for an in-toto statement (spec/v1/envelope.md): application/vnd.in-toto+json.
_DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
# Our runtime-decision predicate type. THESEUS extends in-toto/SLSA (which attest BUILD time)
# to attest RUNTIME decisions onboard (INTEGRATION_SPEC §3.2 — the non-commodity inch). The
# URI is a stable, namespaced predicate identifier (not a network dependency; never fetched).
_THESEUS_PREDICATE_TYPE = "https://forceos.ai/theseus/runtime-decision/v0.1"
# keyid published in every DSSE signature so a verifier can select the right public key.
_DSSE_KEYID = "theseus-record-ed25519"
# Filename of the external attestation artifact (one DSSE envelope per line).
_ATTEST_FILE = "attestations.jsonl"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- atomic / locked persistence helpers -----------------------------------

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write `data` to `path` atomically: temp file in the same dir, fsync, os.replace.

    os.replace() is atomic on POSIX and Windows, so a concurrent reader sees either the
    complete old file or the complete new file -- never a truncated / half-written one.
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic rename within the same filesystem


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


@contextlib.contextmanager
def _dir_lock(out_dir: Path, exclusive: bool):
    """flock a sentinel file in out_dir. Writers take LOCK_EX, readers LOCK_SH.

    This closes the cross-file window between the two atomic replaces (chain.jsonl and
    bundle.json): a reader that holds a shared lock blocks until any in-flight writer has
    finished BOTH replaces, so it always reads a consistent (chain, bundle) pair.

    No-ops (still yields) where fcntl is unavailable -- the atomic single-file replaces still
    prevent torn reads; only the rarer cross-file race is unguarded there.
    """
    if fcntl is None:
        yield
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path = out_dir / ".chain.lock"
    flag = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    # Open r+ so a shared-lock reader never truncates; create on first use.
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, flag)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# ---- Ed25519 record signing (dedicated key; optional, fully offline) --------

def _ed25519_available() -> bool:
    try:
        import cryptography.hazmat.primitives.asymmetric.ed25519  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_signing_key() -> bool:
    """Generate the dedicated Ed25519 record-signing keypair if absent.

    Private key -> referee/keys/record_ed25519.key (0600, gitignored, NEVER committed).
    Public key  -> referee/keys/record_ed25519.pub (safe to distribute/commit).
    Returns True if a usable private key now exists.
    """
    if not _ed25519_available():
        return False
    if _PRIV_PATH.exists():
        return True
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _KEY_DIR.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # Write private key with restrictive perms (0600) BEFORE any bytes land on disk world-readable.
    fd = os.open(str(_PRIV_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(priv_bytes)
    _PUB_PATH.write_bytes(pub_bytes)
    return True


def _load_private_key():
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_private_key(_PRIV_PATH.read_bytes(), password=None)


def _load_public_key_pem(out_dir: Path):
    """Public key precedence: pubkey embedded in the bundle (self-contained verify) ->
    the committed referee/keys/record_ed25519.pub. Returns a loaded key or None."""
    from cryptography.hazmat.primitives import serialization
    bundle_path = out_dir / "bundle.json"
    if bundle_path.exists():
        try:
            b = json.loads(bundle_path.read_text())
            pem = (b.get("signing") or {}).get("ed25519_pubkey_pem")
            if pem:
                return serialization.load_pem_public_key(pem.encode())
        except (ValueError, KeyError, json.JSONDecodeError):
            pass
    if _PUB_PATH.exists():
        return serialization.load_pem_public_key(_PUB_PATH.read_bytes())
    return None


def _sign_leaf_hash(leaf_hash: str) -> str | None:
    """Ed25519-sign a leaf hash with the dedicated record key. Returns base64 sig or None."""
    if not (_ed25519_available() and ensure_signing_key()):
        return None
    sig = _load_private_key().sign(leaf_hash.encode())
    return base64.b64encode(sig).decode()


def _verify_leaf_sig(pubkey, leaf_hash: str, sig_b64: str) -> bool:
    from cryptography.exceptions import InvalidSignature
    try:
        pubkey.verify(base64.b64decode(sig_b64), leaf_hash.encode())
        return True
    except (InvalidSignature, ValueError):
        return False


# ---- in-toto Statement v1 + DSSE envelope (the EXTERNAL recognized attestation) ------------
#
# PIVOT (INTEGRATION_SPEC §4): each sealed leaf is ALSO emitted as a standard in-toto Statement
# wrapped in a DSSE (Dead Simple Signing Envelope), Ed25519-signed with the SAME record key.
# A DoD supply chain (cosign/Sigstore/SLSA) and an AO recognize this format on sight; the Merkle
# chain stays as the internal mechanism. Subject = the model-version-hash or decision id; the
# subject digest binds the statement to the leaf's sealed payload; predicate carries the sealed
# payload itself so the attestation is self-describing and replayable offline.

def _dsse_pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (secure-systems-lab/dsse protocol.md):

        PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body

    LEN is ASCII decimal of the UTF-8 byte length (no leading zeros); SP is a single 0x20.
    We sign the PAE of the SERIALIZED statement body (not its base64), exactly as DSSE mandates,
    so any standard DSSE verifier (e.g. sigstore's go-dsse, cosign) accepts our envelope.
    """
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


def _intoto_statement(leaf: "Leaf", merkle_root: str) -> dict:
    """Build the in-toto Statement v1 for one sealed leaf.

    subject.name   = the decision/model id (kind:obs_id) -- e.g. a model-version-hash or
                     a human ACCEPT/OVERRIDE decision id.
    subject.digest = {sha256: leaf_hash} -- binds the statement to the exact sealed leaf, so a
                     standard attestation verifier matches purely by digest (in-toto §subject).
    predicate      = the sealed payload + chain context (idx/ts/prev_hash/merkle_root + the
                     base64 record). This is the runtime-decision predicate THESEUS contributes.
    """
    return {
        "_type": _INTOTO_STATEMENT_TYPE,
        "subject": [
            {
                "name": f"{leaf.kind}:{leaf.obs_id}",
                "digest": {"sha256": leaf.leaf_hash},
            }
        ],
        "predicateType": _THESEUS_PREDICATE_TYPE,
        "predicate": {
            "kind": leaf.kind,
            "obs_id": leaf.obs_id,
            "idx": leaf.idx,
            "ts": leaf.ts,
            "prev_hash": leaf.prev_hash,
            "leaf_hash": leaf.leaf_hash,
            "merkle_root": merkle_root,
            "record_b64": leaf.record_b64,
        },
    }


def _dsse_sign_statement(statement: dict) -> dict | None:
    """Wrap an in-toto statement in a DSSE envelope, Ed25519-signed over the PAE.

    Returns the envelope dict {payload, payloadType, signatures:[{keyid, sig}]} or None if the
    crypto lib / signing key is unavailable (attestations then simply absent -> still backward
    compatible). Payload is canonical-JSON (sort_keys) so the bytes are reproducible by a verifier.
    """
    if not (_ed25519_available() and ensure_signing_key()):
        return None
    body = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = _load_private_key().sign(_dsse_pae(_DSSE_PAYLOAD_TYPE, body))
    return {
        "payloadType": _DSSE_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode(),
        "signatures": [{"keyid": _DSSE_KEYID, "sig": base64.b64encode(sig).decode()}],
    }


def _dsse_verify_envelope(pubkey, envelope: dict) -> tuple[bool, dict | None]:
    """Verify a DSSE envelope's Ed25519 signature over the PAE; return (ok, decoded_statement).

    Recomputes PAE(payloadType, decoded_payload) and checks at least one signature validates.
    Decodes the in-toto statement from the payload so the caller can match subject digest -> leaf.
    """
    from cryptography.exceptions import InvalidSignature
    try:
        body = base64.b64decode(envelope["payload"])
        payload_type = envelope["payloadType"]
        pae = _dsse_pae(payload_type, body)
        statement = json.loads(body)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return False, None
    sigs = envelope.get("signatures") or []
    for s in sigs:
        try:
            pubkey.verify(base64.b64decode(s["sig"]), pae)
            return True, statement
        except (InvalidSignature, ValueError, KeyError, TypeError):
            continue
    return False, statement


@dataclass(frozen=True)
class Leaf:
    idx: int
    ts: float
    kind: str  # observation | violation | scorecard | bundle_note
    obs_id: str
    record_b64: str
    prev_hash: str
    leaf_hash: str
    sig: str | None = None  # ADDITIVE: base64 Ed25519 signature over leaf_hash (None if unsigned)


class LocalHashChain:
    def __init__(self) -> None:
        self.leaves: list[Leaf] = []

    @staticmethod
    def _leaf_hash(prev_hash: str, kind: str, obs_id: str, record_b64: str) -> str:
        return _sha(f"{prev_hash}|{kind}|{obs_id}|{record_b64}".encode())

    def append(self, kind: str, obs_id: str, record: bytes) -> Leaf:
        prev = self.leaves[-1].leaf_hash if self.leaves else GENESIS
        b64 = base64.b64encode(record).decode()
        leaf_hash = self._leaf_hash(prev, kind, obs_id, b64)
        leaf = Leaf(
            idx=len(self.leaves),
            ts=time.time(),
            kind=kind,
            obs_id=obs_id,
            record_b64=b64,
            prev_hash=prev,
            leaf_hash=leaf_hash,
            sig=_sign_leaf_hash(leaf_hash),
        )
        self.leaves.append(leaf)
        return leaf

    # ---- persistence -------------------------------------------------------
    def write(self, out_dir: Path) -> None:
        """Persist atomically under an exclusive lock.

        Order: attestations.jsonl -> chain.jsonl -> bundle.json. Each via os.replace (atomic
        single-file). The exclusive flock serializes writers and (with verify_dir's shared lock)
        prevents any reader from catching the trio mid-update -> no spurious red tamper SNAP.
        bundle.json is written LAST so leaf_count/merkle_root/head a reader sees in the bundle
        always have their backing chain + attestation rows already on disk.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        with _dir_lock(out_dir, exclusive=True):
            merkle = self.merkle_root()

            # ADDITIVE (PIVOT §4): emit each leaf ALSO as a DSSE-wrapped in-toto attestation --
            # the EXTERNAL recognized artifact. Written FIRST so the chain/bundle a reader sees
            # never reference attestation rows that aren't on disk yet.
            attest_block = self._write_attestations(out_dir, merkle)

            chain_text = "".join(json.dumps(leaf.__dict__) + "\n" for leaf in self.leaves)
            _atomic_write_text(out_dir / "chain.jsonl", chain_text)

            head = self.leaves[-1].leaf_hash if self.leaves else GENESIS
            bundle = {
                "bundle_kind": "referee-proof-bundle/reference-v0",
                "leaf_count": len(self.leaves),
                "chain_head": head,
                "merkle_root": merkle,
                "rfc3161": None,  # flipped live at the event
                "tamper_evident_not_tamper_proof": True,
                "generated_unix": time.time(),
            }
            # ADDITIVE: cryptographic signing block. Embeds the public key so the bundle is a
            # self-contained, offline-verifiable object (zero trust in us, no key fetch needed).
            signing = self._signing_block(head)
            if signing:
                if attest_block:
                    signing["attestations"] = attest_block
                bundle["signing"] = signing
            _atomic_write_text(out_dir / "bundle.json", json.dumps(bundle, indent=2))

    def _write_attestations(self, out_dir: Path, merkle: str) -> dict | None:
        """Emit one DSSE-wrapped in-toto Statement v1 per leaf to attestations.jsonl.

        Returns the bundle sub-block describing the artifact (format/predicateType/count) or None
        if the crypto lib/key is unavailable (then no attestation file is written and the record
        stays exactly backward-compatible: hash-chain + bundle only). Atomic single-file write.
        """
        if not (_ed25519_available() and ensure_signing_key()):
            return None
        lines = []
        emitted = 0
        for leaf in self.leaves:
            env = _dsse_sign_statement(_intoto_statement(leaf, merkle))
            if env is None:  # crypto vanished mid-run; do not emit a half-attested file
                return None
            lines.append(json.dumps(env))
            emitted += 1
        _atomic_write_text(out_dir / _ATTEST_FILE, "".join(l + "\n" for l in lines))
        return {
            "file": _ATTEST_FILE,
            "format": "dsse/in-toto-statement-v1",
            "payloadType": _DSSE_PAYLOAD_TYPE,
            "predicateType": _THESEUS_PREDICATE_TYPE,
            "count": emitted,
        }

    def _signing_block(self, head: str) -> dict | None:
        """Build the additive `signing` block: Ed25519 over the chain head + pubkey + counts.
        cosign signature over the head is attached out-of-band by sign_head_cosign() (optional)."""
        if not (_ed25519_available() and ensure_signing_key()):
            return None
        signed = sum(1 for lf in self.leaves if getattr(lf, "sig", None))
        block = {
            "scheme": "ed25519",
            "key_id": "theseus-record-ed25519",
            "ed25519_pubkey_pem": _PUB_PATH.read_text(),
            "signed_leaf_count": signed,
            "head_sig": _sign_leaf_hash(head) if self.leaves else None,
        }
        return block

    def merkle_root(self) -> str:
        layer = [leaf.leaf_hash for leaf in self.leaves] or [GENESIS]
        while len(layer) > 1:
            if len(layer) % 2:
                layer.append(layer[-1])
            layer = [_sha((layer[i] + layer[i + 1]).encode()) for i in range(0, len(layer), 2)]
        return layer[0]


# ---- optional cosign / Rekor on a connected host (never required for verify) ----

def sign_head_cosign(out_dir: Path, key_path: Path, rekor: bool = False) -> dict | None:
    """OPTIONAL, additive: cosign-sign the chain head with the existing DoD-standard Sigstore
    tool (the same cosign used for Zarf packaging). Writes a detached signature next to the
    record and records its presence in bundle.json under signing.cosign. If rekor=True and a
    host is connected, uploads one transparency-log entry; offline failure is swallowed (the
    Ed25519 + hash-chain verification never depends on cosign or Rekor).

    Returns the cosign sub-block or None if cosign/key unavailable. Honest: this is best-effort
    connectivity sugar layered on top of the always-on offline Ed25519 signature.
    """
    import shutil
    import subprocess

    if shutil.which("cosign") is None or not key_path.exists():
        return None
    bundle_path = out_dir / "bundle.json"
    if not bundle_path.exists():
        return None
    head = json.loads(bundle_path.read_text()).get("chain_head", GENESIS)
    head_file = out_dir / "chain_head.txt"
    _atomic_write_text(head_file, head)
    sig_file = out_dir / "chain_head.cosign.sig"
    cmd = [
        "cosign", "sign-blob", "--yes",
        "--key", str(key_path),
        "--output-signature", str(sig_file),
        f"--tlog-upload={'true' if rekor else 'false'}",
        str(head_file),
    ]
    env = dict(os.environ)
    env.setdefault("COSIGN_PASSWORD", env.get("COSIGN_PASSWORD", ""))
    try:
        subprocess.run(cmd, check=True, capture_output=True, env=env, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None  # connected-host sugar; offline is the normal case
    sub = {
        "tool": "cosign",
        "signature_file": sig_file.name,
        "signed_blob": head_file.name,
        "rekor_uploaded": bool(rekor),
    }
    # Fold into the existing signing block additively, under the same exclusive lock.
    with _dir_lock(out_dir, exclusive=True):
        bundle = json.loads(bundle_path.read_text())
        bundle.setdefault("signing", {})["cosign"] = sub
        _atomic_write_text(bundle_path, json.dumps(bundle, indent=2))
    return sub


# ---- offline verification (anyone can run this; no trust in us required) ----

def verify_dir(out_dir: Path) -> tuple[bool, int | None, str]:
    """Returns (ok, first_bad_leaf_idx, message).

    Backward-compatible + additive: still verifies the prev-hash chain, the Merkle root, and the
    bundle head. If the bundle carries an Ed25519 `signing` block, ALSO verifies every signed
    leaf's signature and the head signature against the embedded public key -- so a tampered byte
    is caught by BOTH the hash chain and a broken cryptographic signature. If attestations.jsonl
    is present (PIVOT §4), ALSO verifies each DSSE-wrapped in-toto Statement: the Ed25519
    signature over the PAE, and that the statement's subject digest binds to the matching leaf --
    so a tampered byte ALSO breaks a recognized attestation, not just our prev-hash. A record
    with no signing block / no attestations file (older format) still verifies exactly as before.

    Reads under a shared flock so it can never catch a writer mid-update (no spurious SNAP).
    """
    chain_path = out_dir / "chain.jsonl"
    bundle_path = out_dir / "bundle.json"
    attest_path = out_dir / _ATTEST_FILE
    with _dir_lock(out_dir, exclusive=False):
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        bundle = json.loads(bundle_path.read_text())
        attest_lines = (
            [line for line in attest_path.read_text().splitlines() if line.strip()]
            if attest_path.exists() else None
        )

    prev = GENESIS
    hashes: list[str] = []
    for row in rows:
        expect = LocalHashChain._leaf_hash(prev, row["kind"], row["obs_id"], row["record_b64"])
        if row["prev_hash"] != prev or row["leaf_hash"] != expect:
            return False, row["idx"], f"chain SNAP at leaf {row['idx']} ({row['kind']}:{row['obs_id']})"
        hashes.append(row["leaf_hash"])
        prev = row["leaf_hash"]

    layer = hashes or [GENESIS]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [_sha((layer[i] + layer[i + 1]).encode()) for i in range(0, len(layer), 2)]
    if bundle["merkle_root"] != layer[0]:
        return False, None, "merkle root mismatch (bundle vs chain)"
    if bundle["chain_head"] != prev:
        return False, None, "chain head mismatch (bundle vs chain)"

    # ---- additive: cryptographic signature verification (only if a signing block exists) ----
    sig_msg = ""
    signing = bundle.get("signing")
    if signing and signing.get("scheme") == "ed25519":
        if not _ed25519_available():
            return False, None, "signing block present but cryptography lib unavailable to verify"
        pubkey = _load_public_key_pem(out_dir)
        if pubkey is None:
            return False, None, "signing block present but no public key available to verify"
        verified = 0
        for row in rows:
            s = row.get("sig")
            if s is None:
                continue  # leaf predates signing; chain hash already proved its integrity
            if not _verify_leaf_sig(pubkey, row["leaf_hash"], s):
                return False, row["idx"], f"Ed25519 signature INVALID at leaf {row['idx']}"
            verified += 1
        head_sig = signing.get("head_sig")
        if head_sig is not None and rows:
            if not _verify_leaf_sig(pubkey, prev, head_sig):
                return False, None, "Ed25519 head signature INVALID"
        cosign_note = " +cosign" if signing.get("cosign") else ""
        sig_msg = f", {verified} Ed25519 sigs OK{cosign_note}"

    # ---- additive: in-toto/DSSE attestation verification (only if attestations.jsonl exists) ----
    # The EXTERNAL recognized artifact. Verify each envelope's DSSE signature AND that its in-toto
    # subject digest binds to the matching leaf -- so tampering breaks a standard attestation too.
    attest_msg = ""
    if attest_lines is not None:
        if not _ed25519_available():
            return False, None, "attestations present but cryptography lib unavailable to verify"
        pubkey = _load_public_key_pem(out_dir)
        if pubkey is None:
            return False, None, "attestations present but no public key available to verify"
        if len(attest_lines) != len(rows):
            return False, None, (
                f"attestation count {len(attest_lines)} != leaf count {len(rows)}"
            )
        by_leaf_hash = {row["leaf_hash"]: row for row in rows}
        attested = 0
        for i, line in enumerate(attest_lines):
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError:
                return False, i, f"attestation {i} is not valid JSON"
            ok_sig, statement = _dsse_verify_envelope(pubkey, envelope)
            if not ok_sig:
                return False, i, f"DSSE attestation signature INVALID at index {i}"
            # in-toto subject-digest binding: the statement must name a sha256 that IS a real leaf,
            # and the leaf at this position must match (ordering preserved 1:1 with the chain).
            try:
                subj = statement["subject"][0]
                claimed = subj["digest"]["sha256"]
                if statement["predicateType"] != _THESEUS_PREDICATE_TYPE:
                    return False, i, f"attestation {i} unexpected predicateType"
                if statement["_type"] != _INTOTO_STATEMENT_TYPE:
                    return False, i, f"attestation {i} not an in-toto Statement v1"
            except (KeyError, IndexError, TypeError):
                return False, i, f"attestation {i} malformed in-toto statement"
            if claimed != rows[i]["leaf_hash"] or claimed not in by_leaf_hash:
                return False, i, f"attestation {i} subject digest does not bind to leaf {rows[i]['idx']}"
            attested += 1
        attest_msg = f", {attested} in-toto/DSSE attestations OK"

    head_short = prev[:12]
    return True, None, (
        f"PASS — {len(rows)} leaves, head {head_short}…, "
        f"merkle {bundle['merkle_root'][:12]}…{sig_msg}{attest_msg}"
    )


def tamper(out_dir: Path, leaf_idx: int) -> str:
    """Flip one byte inside the stored record of leaf N (demo helper)."""
    chain_path = out_dir / "chain.jsonl"
    rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
    row = rows[leaf_idx]
    raw = bytearray(base64.b64decode(row["record_b64"]))
    raw[0] ^= 0x01
    row["record_b64"] = base64.b64encode(bytes(raw)).decode()
    _atomic_write_text(chain_path, "".join(json.dumps(r) + "\n" for r in rows))
    return f"flipped one byte in leaf {leaf_idx}"
