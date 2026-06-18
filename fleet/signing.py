"""Ed25519 signing layer for fleet model-delta attestations.

Each ship holds a private key. Each delta submission is signed as a
minimal in-toto DSSE envelope (JSON, not binary) so it verifies
without a full in-toto install — stdlib + cryptography only.

DSSE structure used here:
  {
    "payload_type": "application/vnd.theseus.model-delta+json",
    "payload": <base64url(UTF-8 JSON of the statement)>,
    "signatures": [{"keyid": "<ship_id>", "sig": "<hex(ed25519 sig)>"}]
  }

The statement payload is a deterministic JSON document encoding the
delta provenance:
  {
    "subject": {"ship_id": ..., "data_hash": ..., "base_model_hash": ...},
    "timestamp_utc": ...,
    "predicate_type": "https://theseus.fleet/delta/v1",
    "predicate": {<any additional fields — e.g. n_samples, feature_names>}
  }

Verification: reconstruct PAE = "DSSEv1" + SP + payload_type + SP + payload
(DSSE spec §2.3) and verify signature. Reject if keyid is not a known ship.

NOTE on interop: this is a self-consistent, DSSE-SHAPED Ed25519 envelope (PAE over the
base64 payload string; hex-encoded signature; snake_case keys). Sign and verify here are
mutually consistent and cryptographically sound for the fleet, but it is NOT byte-for-byte
interoperable with external DSSE verifiers (cosign / go-dsse). The spec-exact, externally
verifiable attestations are in `referee/chain.py` (PAE over the raw serialized body, base64
signature, camelCase). Treat this layer as "Ed25519-signed, DSSE-structured", not as a
drop-in for a third-party DSSE verifier.

The signed statement's predicate carries `model_params_hash` — the fleet brain recomputes
it from the delivered weights and rejects on mismatch, so the signature binds the actual
model weights (not just the metadata) and a valid-key weight-substitution is caught.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def generate_keypair(key_dir: Path, ship_id: str) -> tuple[bytes, bytes]:
    """Generate Ed25519 keypair for ship_id. Save to key_dir. Returns (priv_raw, pub_raw)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, PublicFormat, NoEncryption,
    )
    key_dir.mkdir(parents=True, exist_ok=True)
    priv_key = Ed25519PrivateKey.generate()
    priv_raw = priv_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_raw = priv_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    (key_dir / f"{ship_id}.key").write_bytes(priv_raw)
    (key_dir / f"{ship_id}.pub").write_bytes(pub_raw)
    return priv_raw, pub_raw


def load_private_key(key_dir: Path, ship_id: str) -> bytes:
    return (key_dir / f"{ship_id}.key").read_bytes()


def load_public_key(key_dir: Path, ship_id: str) -> bytes:
    return (key_dir / f"{ship_id}.pub").read_bytes()


def list_known_ships(key_dir: Path) -> list[str]:
    """Return ship_ids that have a .pub file in key_dir."""
    return [p.stem for p in sorted(key_dir.glob("*.pub"))]


# ---------------------------------------------------------------------------
# DSSE helpers
# ---------------------------------------------------------------------------

_PAE_SEP = b" "
_PAE_TYPE = b"DSSEv1"
_PAYLOAD_TYPE = "application/vnd.theseus.model-delta+json"


def _pae(payload_type: str, payload_b64: str) -> bytes:
    """Pre-Authentication Encoding per DSSE §2.3."""
    pt = payload_type.encode()
    pl = payload_b64.encode()
    return (
        _PAE_TYPE + _PAE_SEP
        + str(len(pt)).encode() + _PAE_SEP + pt + _PAE_SEP
        + str(len(pl)).encode() + _PAE_SEP + pl
    )


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = 4 - (len(s) % 4)
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))


# ---------------------------------------------------------------------------
# Statement building and signing
# ---------------------------------------------------------------------------

def build_statement(
    ship_id: str,
    data_hash: str,
    base_model_hash: str,
    n_samples: int,
    feature_names: list[str],
    extra: dict[str, Any] | None = None,
) -> dict:
    """Build the in-toto statement that goes inside the DSSE envelope."""
    stmt: dict[str, Any] = {
        "subject": {
            "ship_id": ship_id,
            "data_hash": data_hash,
            "base_model_hash": base_model_hash,
        },
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "predicate_type": "https://theseus.fleet/delta/v1",
        "predicate": {
            "n_samples": n_samples,
            "feature_names": feature_names,
            **(extra or {}),
        },
    }
    return stmt


def sign_delta(
    statement: dict,
    priv_raw: bytes,
    ship_id: str,
) -> dict:
    """Sign statement and return DSSE envelope dict."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

    payload_json = json.dumps(statement, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url(payload_json.encode())
    to_sign = _pae(_PAYLOAD_TYPE, payload_b64)

    priv_key = Ed25519PrivateKey.from_private_bytes(priv_raw)
    sig_bytes = priv_key.sign(to_sign)

    return {
        "payload_type": _PAYLOAD_TYPE,
        "payload": payload_b64,
        "signatures": [{"keyid": ship_id, "sig": sig_bytes.hex()}],
    }


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_envelope(
    envelope: dict,
    key_dir: Path,
) -> tuple[bool, str, dict | None]:
    """Verify a DSSE envelope against known ship keys.

    Returns (ok, reason, statement_dict | None).
    Rejects if: no signature, unknown ship, bad signature, missing required fields.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature

        sigs = envelope.get("signatures", [])
        if not sigs:
            return False, "no signatures in envelope", None

        payload_b64 = envelope.get("payload", "")
        payload_type = envelope.get("payload_type", "")
        if payload_type != _PAYLOAD_TYPE:
            return False, f"wrong payload_type: {payload_type!r}", None

        to_verify = _pae(payload_type, payload_b64)
        payload_bytes = _b64url_decode(payload_b64)
        statement = json.loads(payload_bytes)

        for sig_entry in sigs:
            keyid = sig_entry.get("keyid", "")
            sig_hex = sig_entry.get("sig", "")

            pub_path = key_dir / f"{keyid}.pub"
            if not pub_path.exists():
                return False, f"unknown ship keyid={keyid!r} (no .pub in key_dir)", None

            pub_raw = pub_path.read_bytes()
            pub_key = Ed25519PublicKey.from_public_bytes(pub_raw)
            try:
                pub_key.verify(bytes.fromhex(sig_hex), to_verify)
            except InvalidSignature:
                return False, f"Ed25519 signature INVALID for keyid={keyid!r}", None

        # Validate required statement fields
        subj = statement.get("subject", {})
        for f in ("ship_id", "data_hash", "base_model_hash"):
            if not subj.get(f):
                return False, f"statement missing subject.{f}", None

        return True, "OK", statement

    except Exception as exc:
        return False, f"verification error: {exc}", None


# ---------------------------------------------------------------------------
# Delta serialization: model params dict → bytes (for chain sealing)
# ---------------------------------------------------------------------------

def params_hash(params: dict[str, Any]) -> str:
    """Deterministic SHA-256 of a params dict for provenance tracking."""
    canon = json.dumps(params, separators=(",", ":"), sort_keys=True, default=_json_default)
    return hashlib.sha256(canon.encode()).hexdigest()


def data_hash(rows: list[dict]) -> str:
    """SHA-256 of the canonical JSON of the data rows (deterministic)."""
    canon = json.dumps(rows, separators=(",", ":"), sort_keys=True, default=_json_default)
    return hashlib.sha256(canon.encode()).hexdigest()


def _json_default(obj: Any) -> Any:
    import numpy as np  # type: ignore
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"not serializable: {type(obj)}")
