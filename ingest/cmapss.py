#!/usr/bin/env python3
"""THESEUS ingest adapter — NASA C-MAPSS turbofan degradation (RUL).

Reads data/datasets/cmapss/train_FD00X.txt (US-Gov public domain). Emits the 3 operating
settings + 21 sensor channels with LAST column = `rul` (remaining useful life =
max_cycle(unit) - current_cycle), the standard C-MAPSS label.

NOTE: demo/retrain.py currently hardcodes TARGET="gt_compressor_decay", so this CSV is
"staged-ready" under the uniform contract (last col = target) — point retrain.py's target
at `rul` to train on it. (Flagged to WARHACKER: parametrize retrain.py TARGET.)
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out" / "cmapss.csv"


def main() -> int:
    ap = argparse.ArgumentParser(description="NASA C-MAPSS -> loop data contract (RUL).")
    ap.add_argument("--subset", default="FD001", choices=["FD001", "FD002", "FD003", "FD004"])
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    src = ROOT / "data" / "datasets" / "cmapss" / f"train_{a.subset}.txt"
    if not src.exists():
        print(f"  source missing: {src}")
        return 1

    feats = ["op_setting_1", "op_setting_2", "op_setting_3"] + [f"sensor_{i}" for i in range(1, 22)]
    raw = []
    maxcycle: dict[int, int] = defaultdict(int)
    for line in src.read_text().splitlines():
        p = line.split()
        if len(p) < 26:
            continue
        unit = int(float(p[0]))
        cycle = int(float(p[1]))
        vals = [float(x) for x in p[2:26]]  # 3 op settings + 21 sensors
        raw.append((unit, cycle, vals))
        maxcycle[unit] = max(maxcycle[unit], cycle)

    rows = []
    for unit, cycle, vals in raw:
        row = dict(zip(feats, vals))
        row["rul"] = maxcycle[unit] - cycle  # last column = target
        rows.append(row)

    fieldnames = feats + ["rul"]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  C-MAPSS {a.subset} -> {out.relative_to(ROOT)} · rows={len(rows)} · "
          f"units={len(maxcycle)} · target=rul (last)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
