#!/usr/bin/env python3
"""THESEUS ingest adapter — UCI #316 Condition-Based Maintenance of Naval Propulsion Plants.

Reads the LOCAL downloaded dataset (data/datasets/cbm_naval_316/, CC BY 4.0) and emits the
loop's data contract: numeric feature columns, LAST column = target.

Target = `gt_compressor_decay` (matches demo/retrain.py TARGET) → this CSV is LOOP-LIVE:
    python3 ingest/cbm.py
    python3 demo/stage_data.py --input ingest/out/cbm.csv
    python3 demo/retrain.py
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "datasets" / "cbm_naval_316" / "UCI CBM Dataset" / "data.txt"
OUT = Path(__file__).resolve().parent / "out" / "cbm.csv"

# 18 whitespace-delimited columns, fixed order per UCI Features.txt.
FEATURES = [
    "lever_position", "ship_speed", "gt_shaft_torque", "gt_rpm", "gas_gen_rpm",
    "stbd_prop_torque", "port_prop_torque", "hp_turbine_exit_temp",
    "compressor_inlet_temp", "compressor_outlet_temp", "hp_turbine_exit_press",
    "compressor_inlet_press", "compressor_outlet_press", "exhaust_gas_press",
    "turbine_injection_ctrl", "fuel_flow",
]
COMP_DECAY = "gt_compressor_decay"   # col 17 — the loop target (LAST column)
TURB_DECAY = "gt_turbine_decay"      # col 18 — secondary UCI target; demo/retrain.py drops it


def main() -> int:
    ap = argparse.ArgumentParser(description="UCI #316 naval CBM -> loop data contract.")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not SRC.exists():
        print(f"  source missing: {SRC}")
        print("  (THESEUS data pull lands it under data/datasets/; gitignored — see docs/research/datasets/DOWNLOADS.md)")
        return 1

    rows = []
    for line in SRC.read_text().splitlines():
        parts = line.split()
        if len(parts) != 18:
            continue
        vals = [float(x) for x in parts]
        row = dict(zip(FEATURES, vals[:16]))
        row[TURB_DECAY] = vals[17]
        row[COMP_DECAY] = vals[16]
        rows.append(row)

    fieldnames = FEATURES + [TURB_DECAY, COMP_DECAY]  # contract: last column = target
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  UCI #316 -> {out.relative_to(ROOT)} · rows={len(rows)} · "
          f"features={len(FEATURES)} (+{TURB_DECAY}) · target={COMP_DECAY} (last)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
