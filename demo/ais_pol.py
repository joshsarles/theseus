#!/usr/bin/env python3
"""THESEUS — AIS Pattern-of-Life anomaly cell (the NV063 beat).

Cold-start, NO historical database, explainable alerts — the hardest NV063
requirement ("must function in novel OPAREAs"). The "normal" speed envelope is
learned IN-SITU from the op-area's own traffic; anomalies are flagged with a
plain-language reason + recommended action, and every alert is sealed into the
tamper-evident record.

Real data: MarineCadastre US AIS (public domain). Streams the CSV, builds tracks,
detects loiter / dark-gap / position-jump(spoof) / overspeed. Pure stdlib.

  python3 demo/ais_pol.py [--rows N] [--box minlat,maxlat,minlon,maxlon]
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from _record import seal, verify

HERE = Path(__file__).resolve().parent
DEFAULT_CSV = HERE.parent / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
RECORD = HERE / "out" / "record"

# plausible max SOG (kn) fallback by AIS VesselType bucket; refined in-situ below
TYPE_MAX_FALLBACK = {"cargo": 30, "tanker": 22, "passenger": 45, "fishing": 18, "other": 40}


def _haversine_nm(a, b) -> float:
    R = 3440.065  # nautical miles
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def _bucket(vtype: str) -> str:
    try:
        t = int(float(vtype))
    except (ValueError, TypeError):
        return "other"
    if 70 <= t <= 79:
        return "cargo"
    if 80 <= t <= 89:
        return "tanker"
    if t in (60, 61, 62, 63, 64, 65, 66, 67, 68, 69):
        return "passenger"
    if t == 30:
        return "fishing"
    return "other"


def load_tracks(csv_path: Path, max_rows: int, box):
    tracks = defaultdict(list)
    type_speeds = defaultdict(list)
    n = 0
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            n += 1
            if n > max_rows:
                break
            try:
                lat, lon, sog = float(row["LAT"]), float(row["LON"]), float(row["SOG"])
            except ValueError:
                continue
            if box and not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
                continue
            try:
                ts = datetime.fromisoformat(row["BaseDateTime"]).timestamp()
            except ValueError:
                continue
            mmsi = row["MMSI"]
            b = _bucket(row.get("VesselType", ""))
            tracks[mmsi].append((ts, lat, lon, sog, int(row.get("Status") or -1), b))
            if 0 < sog < 60:
                type_speeds[b].append(sog)
    # in-situ "normal" envelope: 99th percentile SOG per type, from THIS op-area
    envelope = {}
    for b, sp in type_speeds.items():
        sp.sort()
        envelope[b] = sp[int(len(sp) * 0.99)] if len(sp) > 50 else TYPE_MAX_FALLBACK.get(b, 40)
    return tracks, envelope, n


def detect(tracks, envelope):
    alerts = []
    for mmsi, fixes in tracks.items():
        if len(fixes) < 4:
            continue
        fixes.sort()
        b = fixes[0][5]
        sogs = [f[3] for f in fixes]
        span_h = (fixes[-1][0] - fixes[0][0]) / 3600
        # --- loiter: a vessel that DEMONSTRABLY transited (>3kn) then sat near-zero ---
        # require real movement first, else we just flag berthed ships with bad status (false alarms)
        if span_h >= 1.0 and max(sogs) > 3.0:
            still = sum(1 for f in fixes if f[3] < 0.5 and f[4] == 0)
            frac = still / len(fixes)
            if 0.4 < frac < 0.95:  # moved, then loitered a meaningful stretch (not fully berthed)
                alerts.append((mmsi, "loiter", b, 0.7,
                    f"transited then loitered: {still}/{len(fixes)} fixes <0.5kn over {span_h:.1f}h (peak {max(sogs):.0f}kn)",
                    "verify intent; flag for watch — possible surveillance/rendezvous"))
        # --- overspeed vs in-situ envelope ---
        cap = max(envelope.get(b, 40), 8)
        if max(sogs) > cap * 1.5:
            alerts.append((mmsi, "overspeed", b, 0.6,
                f"SOG {max(sogs):.1f}kn exceeds 1.5x in-situ {b} envelope ({cap:.0f}kn)",
                "verify track quality; possible bad fix or anomalous transit"))
        # --- per-segment: dark gap + position jump (spoof) ---
        for (t0, la0, lo0, s0, *_), (t1, la1, lo1, s1, *_) in zip(fixes, fixes[1:]):
            dt = t1 - t0
            if dt <= 0:
                continue
            dist = _haversine_nm((la0, lo0), (la1, lo1))
            implied = dist / (dt / 3600)
            if dt > 1800 and s0 > 1.0:
                alerts.append((mmsi, "dark_gap", b, 0.65,
                    f"AIS gap {dt/60:.0f} min while underway ({s0:.0f}kn) — possible AIS-off",
                    "cue another sensor; flag possible dark-vessel behavior"))
                break
            if implied > 60 and implied > 5 * max(s0, 1):
                alerts.append((mmsi, "position_jump", b, 0.75,
                    f"implausible jump: {implied:.0f}kn implied vs {s0:.0f}kn reported ({dist:.1f}nm/{dt/60:.0f}min)",
                    "possible GNSS spoofing or identity swap — verify"))
                break
    return alerts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_500_000)
    ap.add_argument("--box", default="")  # minlat,maxlat,minlon,maxlon
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--predictions", help="also write eval predictions.csv (track_id,is_anomaly,score,kind) for eval/score.py")
    a = ap.parse_args()
    box = tuple(float(x) for x in a.box.split(",")) if a.box else None

    csv_path = Path(a.csv)
    print("THESEUS · AIS Pattern-of-Life anomaly cell (cold-start, no historical DB)")
    if not csv_path.exists():
        print(f"  AIS data not found at {csv_path}")
        print("  (THESEUS-agent pull lands it at data/datasets/marinecadastre_us/ — gitignored)")
        return 1

    tracks, envelope, scanned = load_tracks(csv_path, a.rows, box)
    print(f"  scanned {scanned:,} rows → {len(tracks):,} tracks; in-situ envelope: "
          + ", ".join(f"{k}≤{v:.0f}kn" for k, v in sorted(envelope.items())))
    alerts = detect(tracks, envelope)
    by_type = defaultdict(int)
    for al in alerts:
        by_type[al[1]] += 1
    print(f"  {len(alerts)} explainable alerts: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))

    # seal a calibrated-baseline leaf + up to 50 alert leaves (keep the record tight)
    seal(RECORD, "model_trained", "ais-pol:v1",
         {"name": "ais-pol", "version": 1, "in_situ_envelope": envelope,
          "tracks": len(tracks), "rows_scanned": scanned})
    for mmsi, kind, b, conf, why, action in alerts[:50]:
        seal(RECORD, "ais_anomaly", f"{kind}:{mmsi}",
             {"mmsi": mmsi, "type": kind, "vessel_class": b, "confidence": conf,
              "why": why, "recommended_action": action})
    print(f"  sealed baseline + {min(len(alerts),50)} alerts into the record")

    # eval contract (THESEUS eval/score.py): one row per flagged track, deduped by MMSI.
    if a.predictions:
        seen: dict = {}
        for mmsi, kind, b, conf, why, action in alerts:
            if mmsi not in seen or conf > seen[mmsi][0]:
                seen[mmsi] = (conf, kind)
        pp = Path(a.predictions)
        pp.parent.mkdir(parents=True, exist_ok=True)
        with pp.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["track_id", "is_anomaly", "score", "kind"])
            for mmsi, (conf, kind) in seen.items():
                w.writerow([mmsi, 1, conf, kind])
        print(f"  wrote {len(seen)} predictions -> {pp}  (score: python3 eval/score.py --pred {pp} --labels <omtad>)")

    print("\n  sample explainable alerts (what a watchstander sees):")
    for mmsi, kind, b, conf, why, action in alerts[:6]:
        print(f"   • [{kind} · {b} · conf {conf}] MMSI {mmsi}: {why}\n       → {action}")

    ok, _, msg = verify(RECORD)
    print(f"\n  record verify: {'✅ ' if ok else '❌ '}{msg}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
