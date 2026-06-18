#!/usr/bin/env python3
"""Offline record verifier — THESEUS tamper-evident + Ed25519-signed decision record.

Anyone can run this against a sealed record directory with ZERO trust in us: it re-derives the
SHA-256 prev-hash chain, the Merkle root, the bundle head, and (if present) every Ed25519
signature against the public key embedded in the bundle. No network, no key fetch, no daemon.

Usage:
  python -m referee.verify_record --record <dir>
  python referee/verify_record.py --record demo/out          # read-only; safe on a live dir
  python referee/verify_record.py --record <dir> --json       # machine-readable

Exit code 0 = PASS, 1 = FAIL/SNAP. Read-only: it never writes to the record dir.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import the canonical verifier so this script and the live API agree byte-for-byte.
try:
    from referee.chain import verify_dir
except ImportError:  # allow `python referee/verify_record.py` from anywhere
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from referee.chain import verify_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify a THESEUS sealed record (offline).")
    ap.add_argument("--record", required=True, type=Path, help="record directory (chain.jsonl + bundle.json)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    args = ap.parse_args(argv)

    rec: Path = args.record
    chain_p, bundle_p = rec / "chain.jsonl", rec / "bundle.json"
    if not chain_p.exists() or not bundle_p.exists():
        msg = f"no record at {rec} (need chain.jsonl + bundle.json)"
        print(json.dumps({"ok": False, "error": msg}) if args.json else f"FAIL — {msg}")
        return 1

    ok, first_bad, msg = verify_dir(rec)

    # Surface what crypto was actually checked, for an honest on-stage / on-paper claim.
    signing = (json.loads(bundle_p.read_text()).get("signing") or {})
    crypto = {
        "ed25519": signing.get("scheme") == "ed25519",
        "signed_leaf_count": signing.get("signed_leaf_count"),
        "head_signed": signing.get("head_sig") is not None,
        "cosign": bool(signing.get("cosign")),
        "rekor": bool((signing.get("cosign") or {}).get("rekor_uploaded")),
    }

    if args.json:
        print(json.dumps({"ok": ok, "first_bad_leaf": first_bad, "message": msg, "crypto": crypto}, indent=2))
    else:
        flag = "PASS ✓" if ok else "FAIL ✗"
        print(f"{flag} — {msg}")
        if crypto["ed25519"]:
            extra = " +cosign" + (" +rekor" if crypto["rekor"] else "") if crypto["cosign"] else ""
            print(f"  crypto: Ed25519 over {crypto['signed_leaf_count']} leaves"
                  f"{' + head' if crypto['head_signed'] else ''}{extra}")
        else:
            print("  crypto: hash-chain only (no signing block on this record)")
        if not ok and first_bad is not None:
            print(f"  first bad leaf: {first_bad}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
