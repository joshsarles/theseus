#!/usr/bin/env python3
"""THESEUS — surface candidate tracks (with evidence) for ANALYST-CURATED NV063 labels.

OMTAD has no anomaly labels and GFW labels are non-commercial, so the honest path to a real
(non-circular) precision/recall is a small analyst-curated per-OPAREA eval set. This script
does NOT label — it extracts a STRATIFIED candidate set (tracks ais_pol flagged + a sample it
did not) and prints rich, independent evidence per track (declared NavigationStatus + vessel
type + full kinematic profile) so an analyst can adjudicate each from the data, then score
ais_pol against those labels via eval/score.py. Labeling basis (declared-vs-observed + track
shape) is independent of ais_pol's fixed thresholds → breaks the circularity.

  python3 eval/curate_oparea.py [--box minlat,maxlat,minlon,maxlon] [--rows N] [--n-flagged 25 --n-clean 25]
Writes eval/out/curate_candidates.csv (evidence) for the analyst to fill an is_anomaly column.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
PREDS = Path(__file__).resolve().parent / "out" / "ais_pol_preds.csv"
OUT = Path(__file__).resolve().parent / "out" / "curate_candidates.csv"

# AIS NavigationStatus codes (independent declared signal, distinct from ais_pol's kinematics)
STATUS = {0: "underway_engine", 1: "at_anchor", 2: "not_under_command", 3: "restricted_manoeuv",
          5: "moored", 7: "fishing", 8: "underway_sailing"}


def _hav_nm(la0, lo0, la1, lo1):
    R = 3440.065
    a, b, c, d = map(math.radians, (la0, lo0, la1, lo1))
    h = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default="")
    ap.add_argument("--rows", type=int, default=1_500_000)
    ap.add_argument("--n-flagged", type=int, default=25)
    ap.add_argument("--n-clean", type=int, default=25)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    box = tuple(float(x) for x in a.box.split(",")) if a.box else None
    if not SRC.exists():
        print(f"missing {SRC}")
        return 1
    flagged = {}
    if PREDS.exists():
        for r in csv.DictReader(PREDS.open()):
            flagged[str(r["track_id"])] = r.get("kind", "")
    print(f"  ais_pol flagged {len(flagged)} tracks (from {PREDS.name})")

    tracks = defaultdict(list)
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
            if box and not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
                continue
            try:
                st = int(float(row.get("Status") or -1))
            except ValueError:
                st = -1
            try:
                vt = int(float(row.get("VesselType") or -1))
            except ValueError:
                vt = -1
            tracks[row["MMSI"]].append((t, lat, lon, sog, st, vt))

    elig = {m: fx for m, fx in tracks.items() if len(fx) >= 6}  # adjudicable
    flagged_ids = [m for m in elig if m in flagged]
    clean_ids = [m for m in elig if m not in flagged]
    rng = random.Random(63)
    rng.shuffle(flagged_ids)
    rng.shuffle(clean_ids)
    chosen = flagged_ids[:a.n_flagged] + clean_ids[:a.n_clean]

    def evidence(m):
        fx = sorted(elig[m])
        sogs = [x[3] for x in fx]
        span_h = (fx[-1][0] - fx[0][0]) / 3600
        still = sum(1 for x in fx if x[3] < 0.5)
        mg = mj = 0.0
        for (t0, la0, lo0, s0, *_), (t1, la1, lo1, s1, *_) in zip(fx, fx[1:]):
            dt = t1 - t0
            if dt <= 0:
                continue
            mg = max(mg, dt / 60)
            mj = max(mj, _hav_nm(la0, lo0, la1, lo1) / (dt / 3600))
        st_mode = Counter(x[4] for x in fx).most_common(1)[0][0]
        return {"track_id": m, "vessel_type": fx[0][5], "nav_status": STATUS.get(st_mode, st_mode),
                "n_fixes": len(fx), "dur_h": round(span_h, 2),
                "sog_min": round(min(sogs), 1), "sog_mean": round(statistics.fmean(sogs), 1),
                "sog_max": round(max(sogs), 1), "still_frac": round(still / len(fx), 2),
                "max_gap_min": round(mg, 1), "max_jump_kn": round(mj, 1),
                "aispol_flag": 1 if m in flagged else 0, "aispol_kind": flagged.get(m, ""),
                "is_anomaly": ""}  # <- analyst fills this

    rows = [evidence(m) for m in chosen]
    cols = ["track_id", "vessel_type", "nav_status", "n_fixes", "dur_h", "sog_min", "sog_mean",
            "sog_max", "still_frac", "max_gap_min", "max_jump_kn", "aispol_flag", "aispol_kind", "is_anomaly"]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  candidates -> {out} · {len(rows)} tracks ({len(flagged_ids[:a.n_flagged])} flagged + {len(clean_ids[:a.n_clean])} clean) · eligible pool={len(elig)}")
    print("  --- evidence (adjudicate is_anomaly from THIS, independent of ais_pol) ---")
    for r in rows:
        print(f"   {r['track_id']} ty{r['vessel_type']:>3} {r['nav_status']:<18} "
              f"fix{r['n_fixes']:>3} {r['dur_h']:>5}h sog[{r['sog_min']},{r['sog_mean']},{r['sog_max']}] "
              f"still{r['still_frac']} gap{r['max_gap_min']}m jump{r['max_jump_kn']}kn "
              f"[ais_pol:{r['aispol_kind'] or '-'}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
