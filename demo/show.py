#!/usr/bin/env python3
"""THESEUS — watchstander board (the human-in-command surface).

Renders what the model-delivery loop + the AIS Pattern-of-Life cell sealed into the
tamper-evident record: machinery (CBM) model health, flagged contacts as recommendation
cards a watch officer accepts/overrides, and the record integrity. Decision-support only —
Theseus recommends; the human decides; nothing is actioned automatically.

  python3 demo/show.py        # reads demo/out/record (run the loop + ais_pol first)
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

from _record import verify

HERE = Path(__file__).resolve().parent
RECORD = HERE / "out" / "record"
BAR = "─" * 72


def _leaves() -> list[dict]:
    cp = RECORD / "chain.jsonl"
    if not cp.exists():
        return []
    out = []
    for line in cp.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        try:
            row["data"] = json.loads(base64.b64decode(row["record_b64"]))
        except Exception:
            row["data"] = {}
        out.append(row)
    return out


def main() -> int:
    leaves = _leaves()
    if not leaves:
        print("No record yet. Run:  bash demo/run.sh   and   python3 demo/ais_pol.py")
        return 1

    by_kind: dict[str, list[dict]] = {}
    for lf in leaves:
        by_kind.setdefault(lf["kind"], []).append(lf)

    print(f"\n{BAR}\n  THESEUS — SHIP-STATE BOARD   (decision-support · human-in-command)\n{BAR}")

    # --- MACHINERY (CBM) ---
    promo = by_kind.get("model_promoted", [])
    print("\n  ⚙  MACHINERY / HM&E")
    if promo:
        d = promo[-1]["data"]
        print(f"     model {d.get('version','?')} serving · RMSE {d.get('rmse','?')} · {d.get('framework','?')}")
        print(f"     gas-turbine compressor-decay model nominal; {len(promo)} promotion(s) on record")
    else:
        print("     (no model promoted yet)")

    # --- CONTACTS (AIS Pattern-of-Life) ---
    alerts = by_kind.get("ais_anomaly", [])
    print(f"\n  🛰  CONTACTS / PATTERN-OF-LIFE   —   {len(alerts)} flagged, awaiting watch review")
    for lf in alerts[:8]:
        d = lf["data"]
        print(f"     ┌ [{d.get('type','?')} · {d.get('vessel_class','?')} · conf {d.get('confidence','?')}] MMSI {d.get('mmsi','?')}")
        print(f"     │  why : {d.get('why','?')}")
        print(f"     └  RECOMMEND → {d.get('recommended_action','?')}   [ ACCEPT / OVERRIDE ]")
    if len(alerts) > 8:
        print(f"     … +{len(alerts)-8} more")

    # --- HUMAN-IN-COMMAND ---
    pending = len(alerts)
    print(f"\n  👤 HUMAN-IN-COMMAND")
    print(f"     {pending} recommendation(s) pending watchstander ACCEPT/OVERRIDE.")
    print("     Theseus recommends; the watch officer decides. Nothing is actioned automatically.")

    # --- RECORD INTEGRITY (the moat) ---
    ok, bad, msg = verify(RECORD)
    staged = len(by_kind.get("data_staged", []))
    trained = len(by_kind.get("model_trained", []))
    print(f"\n  🔒 RECORD INTEGRITY")
    print(f"     {'✅ ' if ok else '❌ '}{msg}")
    print(f"     events sealed: data_staged={staged} model_trained={trained} model_promoted={len(promo)} ais_anomaly={len(alerts)}")
    print(f"\n{BAR}\n")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
