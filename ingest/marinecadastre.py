#!/usr/bin/env python3
"""THESEUS ingest adapter — MarineCadastre US AIS -> per-track feature table.

Reads data/datasets/marinecadastre_us/AIS_2024_01_01.csv (US public domain, ~7.3M rows).
Emits one row per vessel track with numeric kinematic features; LAST column =
`weak_anomaly_heuristic` (1/0).

⚠ WEAK SUPERVISION, NOT GROUND TRUTH. The label is distilled from transparent
Pattern-of-Life rules (loiter / dark-gap / overspeed / position-jump) — the same rule
family as demo/ais_pol.py. Use it only to train a fast model that MIMICS the rule detector.
For HONEST anomaly metrics use OMTAD-labeled data via the eval/ harness. Raw AIS carries
no anomaly ground truth, so we never claim this column as such.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
OUT = Path(__file__).resolve().parent / "out" / "marinecadastre.csv"


def _haversine_nm(la0: float, lo0: float, la1: float, lo1: float) -> float:
    R = 3440.065
    a, b, c, d = map(math.radians, (la0, lo0, la1, lo1))
    h = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def main() -> int:
    ap = argparse.ArgumentParser(description="MarineCadastre AIS -> per-track feature table.")
    ap.add_argument("--rows", type=int, default=1_500_000, help="max raw AIS rows to scan")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not SRC.exists():
        print(f"  source missing: {SRC}")
        return 1

    tracks: dict[str, list] = defaultdict(list)
    n = 0
    with SRC.open() as f:
        for row in csv.DictReader(f):
            n += 1
            if n > a.rows:
                break
            try:
                lat, lon, sog = float(row["LAT"]), float(row["LON"]), float(row["SOG"])
                t = datetime.fromisoformat(row["BaseDateTime"]).timestamp()
            except (ValueError, KeyError):
                continue
            try:
                vt = int(float(row.get("VesselType") or -1))
            except ValueError:
                vt = -1
            try:
                st = int(float(row.get("Status") or -1))
            except ValueError:
                st = -1
            tracks[row["MMSI"]].append((t, lat, lon, sog, st, vt))

    rows = []
    for mmsi, fx in tracks.items():
        if len(fx) < 4:
            continue
        fx.sort()
        sogs = [f[3] for f in fx]
        span_h = (fx[-1][0] - fx[0][0]) / 3600
        lat_span = max(f[1] for f in fx) - min(f[1] for f in fx)
        lon_span = max(f[2] for f in fx) - min(f[2] for f in fx)
        max_gap = 0.0
        max_implied = 0.0
        for (t0, la0, lo0, s0, *_), (t1, la1, lo1, s1, *_) in zip(fx, fx[1:]):
            dt = t1 - t0
            if dt <= 0:
                continue
            max_gap = max(max_gap, dt / 60)
            max_implied = max(max_implied, _haversine_nm(la0, lo0, la1, lo1) / (dt / 3600))
        vt = fx[0][5]
        # transparent weak rules (same family as demo/ais_pol.py — NOT ground truth)
        still = sum(1 for f in fx if f[3] < 0.5 and f[4] == 0)
        loiter = span_h >= 1.0 and max(sogs) > 3.0 and 0.4 < still / len(fx) < 0.95
        dark_gap = max_gap > 30 and max(sogs) > 1.0
        overspeed = max(sogs) > 60
        jump = max_implied > 60 and max_implied > 5 * max(max(sogs), 1)
        weak = 1 if (loiter or dark_gap or overspeed or jump) else 0
        rows.append({
            "n_fixes": len(fx),
            "duration_h": round(span_h, 3),
            "mean_sog": round(statistics.fmean(sogs), 3),
            "max_sog": round(max(sogs), 3),
            "sog_std": round(statistics.pstdev(sogs), 3) if len(sogs) > 1 else 0.0,
            "lat_span": round(lat_span, 4),
            "lon_span": round(lon_span, 4),
            "max_gap_min": round(max_gap, 1),
            "max_implied_speed": round(max_implied, 1),
            "vessel_type": vt,
            "weak_anomaly_heuristic": weak,
        })

    fieldnames = ["n_fixes", "duration_h", "mean_sog", "max_sog", "sog_std", "lat_span",
                  "lon_span", "max_gap_min", "max_implied_speed", "vessel_type",
                  "weak_anomaly_heuristic"]  # contract: last column = target
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    pos = sum(r["weak_anomaly_heuristic"] for r in rows)
    print(f"  MarineCadastre -> {out.relative_to(ROOT)} · tracks={len(rows)} (scanned {n:,}) · "
          f"weak_anomaly={pos} · target=weak_anomaly_heuristic (last)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
