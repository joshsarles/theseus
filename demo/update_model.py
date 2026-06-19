#!/usr/bin/env python3
"""THESEUS demo — STEP 3: Update the local model (the edge node / Pi).

Promotes the latest registered version to the live local slot (demo/models/current/),
keeps the previous version for rollback-under-DDIL, seals a `model_promoted` leaf,
then runs an offline verify of the whole record -> PASS.

This is what runs on a Raspberry Pi: pull the staged/registered model, swap it in,
prove the swap. No shore round-trip required.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from _record import seal, verify

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry" / "theseus-cbm"
CURRENT = HERE / "models" / "current"
RECORD = HERE / "out" / "record"


def _latest() -> Path | None:
    vs = sorted((p for p in REGISTRY.glob("v*") if p.name[1:].isdigit()),
                key=lambda p: int(p.name[1:]))
    return vs[-1] if vs else None


def main() -> int:
    print("THESEUS demo · STEP 3 — Update local model (edge node)")
    latest = _latest()
    if latest is None:
        print("  no registered model — run retrain.py first")
        return 1
    meta = json.loads((latest / "meta.json").read_text())

    # keep the prior live model for rollback-under-DDIL
    if CURRENT.exists():
        prev_meta = json.loads((CURRENT / "meta.json").read_text())
        rollback = HERE / "models" / "previous"
        if rollback.exists():
            shutil.rmtree(rollback)
        shutil.copytree(CURRENT, rollback)
        print(f"  kept previous (v{prev_meta['version']}) -> models/previous (rollback ready)")
        shutil.rmtree(CURRENT)

    shutil.copytree(latest, CURRENT, dirs_exist_ok=True)   # idempotent — closes the rmtree/copytree race (flaky FileExistsError)
    print(f"  promoted v{meta['version']} -> models/current  (RMSE={meta['rmse']})")

    seal(RECORD, "model_promoted", f"theseus-cbm:v{meta['version']}",
         {"version": meta["version"], "rmse": meta["rmse"],
          "model_sha256": meta["model_sha256"], "framework": meta["framework"],
          # carry the REAL held-out residual history into the promoted leaf so /api/state
          # can serve machinery.residual_history (the sparkline) straight from the record.
          "residual_history": meta.get("residual_history", [])})
    print("  sealed model_promoted")

    ok, bad, msg = verify(RECORD)
    print(f"  record verify: {'✅ ' if ok else '❌ '}{msg}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
