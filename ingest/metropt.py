#!/usr/bin/env python3
"""THESEUS ingest adapter — MetroPT-3 air-compressor telemetry (REAL failures).

Reads data/datasets/metropt3/MetroPT3(AirCompressor).csv (CC BY 4.0, ~1.5M rows @ 1 Hz).
Aggregates to fixed time windows (default 600 s) of per-sensor means; LAST column =
`is_anomaly` (1 if the window overlaps a documented air-leak failure window, else 0).

Labels are the COMPANY-REPORTED air-leak windows from the dataset's Data Description
(Veloso et al., Sci Data 2022) — real failure reports, NOT invented. The raw stream is
unlabeled; these four windows are the published ground truth.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "datasets" / "metropt3" / "MetroPT3(AirCompressor).csv"
OUT = Path(__file__).resolve().parent / "out" / "metropt.csv"

SENSORS = ["TP2", "TP3", "H1", "DV_pressure", "Reservoirs", "Oil_temperature", "Motor_current",
           "COMP", "DV_eletric", "Towers", "MPG", "LPS", "Pressure_switch", "Oil_level",
           "Caudal_impulses"]

# Company-reported air-leak failure windows (dataset Data Description table).
FAILURES = [
    ("2020-04-18 00:00:00", "2020-04-18 23:59:00"),
    ("2020-05-29 23:30:00", "2020-05-30 06:00:00"),
    ("2020-06-05 10:00:00", "2020-06-07 14:30:00"),
    ("2020-07-15 14:30:00", "2020-07-15 19:00:00"),
]


def _ts(s: str) -> float:
    return datetime.fromisoformat(s).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser(description="MetroPT-3 -> loop data contract (windowed anomaly).")
    ap.add_argument("--window", type=int, default=600, help="aggregation window (seconds)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not SRC.exists():
        print(f"  source missing: {SRC}")
        return 1

    fails = [(_ts(s), _ts(e)) for s, e in FAILURES]
    sums: dict[int, list[float]] = defaultdict(lambda: [0.0] * len(SENSORS))
    counts: dict[int, int] = defaultdict(int)

    with SRC.open() as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.fromisoformat(row["timestamp"]).timestamp()
            except (ValueError, KeyError):
                continue
            b = int(t // a.window)
            acc = sums[b]
            ok = True
            for i, s in enumerate(SENSORS):
                try:
                    acc[i] += float(row[s])
                except (ValueError, KeyError):
                    ok = False
                    break
            if ok:
                counts[b] += 1

    rows = []
    for b in sorted(counts):
        n = counts[b]
        center = b * a.window + a.window / 2
        is_anom = 1 if any(s <= center <= e for s, e in fails) else 0
        row = {s: round(sums[b][i] / n, 4) for i, s in enumerate(SENSORS)}
        row["is_anomaly"] = is_anom
        rows.append(row)

    fieldnames = SENSORS + ["is_anomaly"]  # contract: last column = target
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    pos = sum(r["is_anomaly"] for r in rows)
    print(f"  MetroPT-3 -> {out.relative_to(ROOT)} · windows={len(rows)} ({a.window}s) · "
          f"anomaly={pos} · target=is_anomaly (last)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
