"""Seal demo events into the Theseus tamper-evident record (referee/chain.py).

Each demo step (stage -> retrain -> update) appends one leaf to a hash-chained,
offline-verifiable record. This is the moat: every model promotion is provable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from referee.chain import Leaf, LocalHashChain, verify_dir  # noqa: E402


def _load(out_dir: Path) -> LocalHashChain:
    """Reconstruct an existing chain so we can append across separate scripts."""
    chain = LocalHashChain()
    cp = out_dir / "chain.jsonl"
    if cp.exists():
        for line in cp.read_text().splitlines():
            if line.strip():
                chain.leaves.append(Leaf(**json.loads(line)))
    return chain


def seal(out_dir: Path, kind: str, obs_id: str, record: dict) -> str:
    """Append one record leaf and persist. Returns the leaf hash."""
    out_dir.mkdir(parents=True, exist_ok=True)
    chain = _load(out_dir)
    leaf = chain.append(kind, obs_id, json.dumps(record, sort_keys=True).encode())
    chain.write(out_dir)
    return leaf.leaf_hash


def verify(out_dir: Path) -> tuple[bool, int | None, str]:
    return verify_dir(out_dir)
