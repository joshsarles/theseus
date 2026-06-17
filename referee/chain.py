"""Reference tamper-evident record: SHA-256 prev-hash chain + Merkle root + offline verify.

Generic primitives only (AGPL-safe). At the event this seam swaps to the production
Ed25519-signed ledger via the same append/verify interface (retained IP, via wheels).
Tamper-EVIDENT, not tamper-proof.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

GENESIS = "0" * 64


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Leaf:
    idx: int
    ts: float
    kind: str  # observation | violation | scorecard | bundle_note
    obs_id: str
    record_b64: str
    prev_hash: str
    leaf_hash: str


class LocalHashChain:
    def __init__(self) -> None:
        self.leaves: list[Leaf] = []

    @staticmethod
    def _leaf_hash(prev_hash: str, kind: str, obs_id: str, record_b64: str) -> str:
        return _sha(f"{prev_hash}|{kind}|{obs_id}|{record_b64}".encode())

    def append(self, kind: str, obs_id: str, record: bytes) -> Leaf:
        prev = self.leaves[-1].leaf_hash if self.leaves else GENESIS
        b64 = base64.b64encode(record).decode()
        leaf = Leaf(
            idx=len(self.leaves),
            ts=time.time(),
            kind=kind,
            obs_id=obs_id,
            record_b64=b64,
            prev_hash=prev,
            leaf_hash=self._leaf_hash(prev, kind, obs_id, b64),
        )
        self.leaves.append(leaf)
        return leaf

    # ---- persistence -------------------------------------------------------
    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "chain.jsonl").open("w") as f:
            for leaf in self.leaves:
                f.write(json.dumps(leaf.__dict__) + "\n")
        (out_dir / "bundle.json").write_text(
            json.dumps(
                {
                    "bundle_kind": "referee-proof-bundle/reference-v0",
                    "leaf_count": len(self.leaves),
                    "chain_head": self.leaves[-1].leaf_hash if self.leaves else GENESIS,
                    "merkle_root": self.merkle_root(),
                    "rfc3161": None,  # flipped live at the event
                    "tamper_evident_not_tamper_proof": True,
                    "generated_unix": time.time(),
                },
                indent=2,
            )
        )

    def merkle_root(self) -> str:
        layer = [leaf.leaf_hash for leaf in self.leaves] or [GENESIS]
        while len(layer) > 1:
            if len(layer) % 2:
                layer.append(layer[-1])
            layer = [_sha((layer[i] + layer[i + 1]).encode()) for i in range(0, len(layer), 2)]
        return layer[0]


# ---- offline verification (anyone can run this; no trust in us required) ----

def verify_dir(out_dir: Path) -> tuple[bool, int | None, str]:
    """Returns (ok, first_bad_leaf_idx, message)."""
    chain_path = out_dir / "chain.jsonl"
    bundle_path = out_dir / "bundle.json"
    rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
    prev = GENESIS
    hashes: list[str] = []
    for row in rows:
        expect = LocalHashChain._leaf_hash(prev, row["kind"], row["obs_id"], row["record_b64"])
        if row["prev_hash"] != prev or row["leaf_hash"] != expect:
            return False, row["idx"], f"chain SNAP at leaf {row['idx']} ({row['kind']}:{row['obs_id']})"
        hashes.append(row["leaf_hash"])
        prev = row["leaf_hash"]
    bundle = json.loads(bundle_path.read_text())
    layer = hashes or [GENESIS]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [_sha((layer[i] + layer[i + 1]).encode()) for i in range(0, len(layer), 2)]
    if bundle["merkle_root"] != layer[0]:
        return False, None, "merkle root mismatch (bundle vs chain)"
    if bundle["chain_head"] != prev:
        return False, None, "chain head mismatch (bundle vs chain)"
    return True, None, f"PASS — {len(rows)} leaves, head {prev[:12]}…, merkle {bundle['merkle_root'][:12]}…"


def tamper(out_dir: Path, leaf_idx: int) -> str:
    """Flip one byte inside the stored record of leaf N (demo helper)."""
    chain_path = out_dir / "chain.jsonl"
    rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
    row = rows[leaf_idx]
    raw = bytearray(base64.b64decode(row["record_b64"]))
    raw[0] ^= 0x01
    row["record_b64"] = base64.b64encode(bytes(raw)).decode()
    chain_path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return f"flipped one byte in leaf {leaf_idx}"
