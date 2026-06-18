#!/usr/bin/env python3
"""Seal the cross-gap delivery into the Theseus tamper-evident record, then
verify the record offline.

Calls the demo's record API directly (demo/_record.seal) with kind
"shore_to_ship_sync" and a payload that makes the delivery provable:
  model name, shore version, ship version, bundle path, bundle SHA-256.

After sealing we run referee.chain.verify_dir on our OWN record dir
(deploy/mlflow-sync/out/record) so the chain + merkle root check is PASS.

Usage:
    python seal_transfer.py --model theseus-cbm --shore-version 1 \
        --ship-version 1 --bundle <bundle> --bundle-sha256 <hex> \
        --record-dir <dir>
Prints a JSON line with the leaf hash + verify result.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "demo"))    # demo/_record.py
sys.path.insert(0, str(REPO))             # referee/chain.py

from _record import seal  # noqa: E402  (demo/_record.py — the record API)
from referee.chain import verify_dir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--shore-version", required=True)
    ap.add_argument("--ship-version", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--bundle-sha256", required=True)
    ap.add_argument("--record-dir", required=True)
    args = ap.parse_args()

    record_dir = Path(args.record_dir)
    payload = {
        "model_name": args.model,
        "shore_version": int(args.shore_version),
        "ship_version": int(args.ship_version),
        "transfer_bundle": str(args.bundle),
        "bundle_sha256": args.bundle_sha256,
        "pattern": "BDTS/CANES file-bundle cross-domain transfer (DDIL)",
        "sealed_unix": time.time(),
    }
    obs_id = f"{args.model}:shore_v{args.shore_version}->ship_v{args.ship_version}"
    leaf = seal(record_dir, "shore_to_ship_sync", obs_id, payload)

    ok, bad_idx, msg = verify_dir(record_dir)
    print(json.dumps({
        "ok": True,
        "leaf_hash": leaf,
        "obs_id": obs_id,
        "record_dir": str(record_dir),
        "verify_ok": bool(ok),
        "verify_msg": msg,
        "first_bad_leaf": bad_idx,
    }))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
