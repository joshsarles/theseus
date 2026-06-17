#!/usr/bin/env python3
"""THESEUS — weak anomaly labels for the NV063 eval SANITY CHECK (track_id, is_anomaly).

⚠ WEAK SUPERVISION, NOT GROUND TRUTH. Applies transparent Pattern-of-Life rules
(loiter / dark-gap / overspeed / position-jump) to MarineCadastre AIS and emits one
`(track_id=MMSI, is_anomaly)` row per track (>=4 fixes), keyed by MMSI so it joins
`demo/ais_pol.py --predictions`.

Because this is the SAME RULE FAMILY as ais_pol, scoring ais_pol against these labels is
~CIRCULAR: it validates the eval plumbing and measures rule-implementation *agreement*,
**not detection skill**. Real NV063 metrics need OMTAD ground truth (see
`docs/research/datasets/DATASETS.md` §6). Thresholds here intentionally differ slightly
from ais_pol (fixed 60 kn overspeed vs ais_pol's in-situ envelope) so the score reflects
genuine agreement/disagreement, not identity.

  python3 eval/make_weak_labels.py [--rows N] [--box minlat,maxlat,minlon,maxlon] [--out PATH]
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
OUT = Path(__file__).resolve().parent / "out" / "weak_labels.csv"


def _hav_nm(la0, lo0, la1, lo1):
    R = 3440.065
    a, b, c, d = map(math.radians, (la0, lo0, la1, lo1))
    h = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def main() -> int:
    ap = argparse.ArgumentParser(description="Weak PoL labels (track_id,is_anomaly) for eval sanity check.")
    ap.add_argument("--rows", type=int, default=1_500_000)
    ap.add_argument("--box", default="")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    box = tuple(float(x) for x in a.box.split(",")) if a.box else None
    src = Path(a.csv)
    if not src.exists():
        print(f"  AIS not found: {src}")
        return 1

    tracks: dict[str, list] = defaultdict(list)
    n = 0
    with src.open() as f:
        for row in csv.DictReader(f):
            n += 1
            if n > a.rows:
                break
            try:
                lat, lon, sog = float(row["LAT"]), float(row["LON"]), float(row["SOG"])
                ts = datetime.fromisoformat(row["BaseDateTime"]).timestamp()
            except (ValueError, KeyError):
                continue
            if box and not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
                continue
            try:
                st = int(float(row.get("Status") or -1))
            except ValueError:
                st = -1
            tracks[row["MMSI"]].append((ts, lat, lon, sog, st))

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = pos = 0
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["track_id", "is_anomaly"])
        for mmsi, fx in tracks.items():
            if len(fx) < 4:
                continue
            fx.sort()
            total += 1
            sogs = [x[3] for x in fx]
            span_h = (fx[-1][0] - fx[0][0]) / 3600
            still = sum(1 for x in fx if x[3] < 0.5 and x[4] == 0)
            loiter = span_h >= 1.0 and max(sogs) > 3.0 and 0.4 < still / len(fx) < 0.95
            mg = mi = 0.0
            for (t0, la0, lo0, s0, _), (t1, la1, lo1, s1, _) in zip(fx, fx[1:]):
                dt = t1 - t0
                if dt <= 0:
                    continue
                mg = max(mg, dt / 60)
                mi = max(mi, _hav_nm(la0, lo0, la1, lo1) / (dt / 3600))
            dark = mg > 30 and max(sogs) > 1.0
            over = max(sogs) > 60
            jump = mi > 60 and mi > 5 * max(max(sogs), 1)
            weak = 1 if (loiter or dark or over or jump) else 0
            pos += weak
            w.writerow([mmsi, weak])
    print(f"  weak labels -> {a.out} · tracks={total} · positive={pos} "
          f"({100*pos/max(total,1):.1f}%) · scanned {n:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
