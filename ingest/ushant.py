#!/usr/bin/env python3
"""THESEUS ingest adapter — Ushant AIS (Brittany, France) -> MarineCadastre-style CSV.

Normalizes the Zenodo Ushant trajectory dataset (Gloaguen et al., 2019 — 6 months
of AIS around the Ushant Traffic Separation Scheme, West of France; 18,603
per-vessel trajectory files, >7M GPS fixes) into the *exact* column schema that
`demo/ais_pol.py --csv` expects:

    MMSI, LAT, LON, SOG, BaseDateTime   (ISO-8601)

The point of this adapter is a CROSS-REGION cold-start test: run the UNCHANGED
ais_pol detector — which builds its "normal" speed envelope IN-SITU from whatever
op-area it is pointed at — on a region with totally different traffic (a high-speed
shipping lane off Brittany) and totally different source schema. If it works with
no code changes, the cold-start design generalizes and is not overfit to US data.

SOURCE SCHEMA (semicolon-delimited, one file per vessel track, header
`"x";"y";"vx";"vy";"t"`), per the dataset READ_ME:
  x  = longitude (decimal degrees)
  y  = latitude  (decimal degrees)
  vx = x-velocity in KNOTS  (taken from the AIS message, not computed)
  vy = y-velocity in KNOTS  (taken from the AIS message, not computed)
  t  = seconds since the START of that trajectory (relative; first row t=0)

HONEST UNIT / FIELD MAPPING (no silent conversions):
  * SOG  := sqrt(vx^2 + vy^2)   — knots in, knots out. ais_pol treats SOG as knots,
            so this is a like-for-like field. No conversion.
  * LAT  := y, LON := x         — both already decimal degrees. No conversion.
  * BaseDateTime := ANCHOR_EPOCH + (per-track stagger) + t seconds, ISO-8601.
            The dataset gives only RELATIVE seconds (no wall-clock date), so we
            synthesize absolute timestamps. ais_pol only ever uses time DELTAS
            within a single MMSI track (gaps, implied speed), so the absolute
            anchor is immaterial to detection; we stagger tracks by day to keep
            timestamps human-sane and reproducible.
  * MMSI := synthetic, derived 1:1 from the trajectory file index (one file = one
            track in the source). The dataset is anonymized (no real MMSI). We make
            it look MMSI-shaped (9 digits) and stable/reproducible.
  * VesselType: NOT in the source -> OMITTED. ais_pol falls back to the "other"
            bucket + TYPE_MAX_FALLBACK. This is the honest cold-start case.
  * Status:     NOT in the source -> OMITTED (defaults to -1 in ais_pol). NOTE: the
            loiter rule keys on Status==0 (underway), so loiter is effectively
            SUPPRESSED for Ushant. We report this caveat in the validation doc
            rather than fabricate a Status column.

Output: data/datasets/ushant/ushant_normalized.csv (gitignored; large).
Run the detector with NO code changes:
    python3 demo/ais_pol.py --csv data/datasets/ushant/ushant_normalized.csv --rows N
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "datasets" / "ushant" / "data"
OUT = ROOT / "data" / "datasets" / "ushant" / "ushant_normalized.csv"

# Fixed, reproducible wall-clock anchor. The dataset is 6 months of 2015-2016-era
# AIS; the exact date is not published, so we anchor at a neutral epoch. Only
# WITHIN-track deltas matter to ais_pol, so this choice does not affect detection.
ANCHOR = datetime(2016, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_TRAJ_RE = re.compile(r"traj_(\d+)\.txt$")


def _synthetic_mmsi(idx: int) -> str:
    """Stable, reproducible, MMSI-shaped (9-digit) id from the file index.

    Prefix 990 keeps it clearly synthetic (990 is an aids-to-navigation MID range,
    so it can never collide with a real-vessel MMSI in a side-by-side).
    """
    return f"990{idx % 1_000_000:06d}"


def _iter_track(path: Path):
    """Yield (lat, lon, sog_kn, t_rel_s) for one Ushant trajectory file."""
    with path.open() as f:
        header = f.readline()  # "x";"y";"vx";"vy";"t"
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(";")
            if len(parts) < 5:
                continue
            try:
                x = float(parts[0])   # longitude
                y = float(parts[1])   # latitude
                vx = float(parts[2])  # knots
                vy = float(parts[3])  # knots
                t = float(parts[4])   # seconds since track start
            except ValueError:
                continue
            sog = math.hypot(vx, vy)
            yield y, x, sog, t


def main() -> int:
    ap = argparse.ArgumentParser(description="Ushant AIS -> MarineCadastre-style CSV for ais_pol.py")
    ap.add_argument("--max-tracks", type=int, default=0,
                    help="cap number of trajectory files processed (0 = all 18,603)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--box", default="",
                    help="optional minlat,maxlat,minlon,maxlon spatial filter (decimal deg)")
    a = ap.parse_args()

    if not SRC_DIR.is_dir():
        print(f"  source missing: {SRC_DIR}")
        print("  (expected the Zenodo Ushant trajectory files at data/datasets/ushant/data/traj_*.txt)")
        return 1

    box = tuple(float(v) for v in a.box.split(",")) if a.box else None

    # sort by numeric trajectory index for deterministic, reproducible output
    files = sorted(SRC_DIR.glob("traj_*.txt"),
                   key=lambda p: int(_TRAJ_RE.search(p.name).group(1)) if _TRAJ_RE.search(p.name) else 0)
    if a.max_tracks > 0:
        files = files[:a.max_tracks]

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    n_tracks = 0
    n_rows = 0
    n_dropped_box = 0
    sog_max = 0.0
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["MMSI", "LAT", "LON", "SOG", "BaseDateTime"])
        for f in files:
            m = _TRAJ_RE.search(f.name)
            idx = int(m.group(1)) if m else n_tracks
            mmsi = _synthetic_mmsi(idx)
            # stagger each track's anchor by ~1h so absolute timestamps stay sane
            # across the synthetic concatenation; within-track deltas are exact.
            base = ANCHOR + timedelta(hours=idx % 4380)  # spread over ~6 months
            wrote_any = False
            for lat, lon, sog, t_rel in _iter_track(f):
                if box and not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
                    n_dropped_box += 1
                    continue
                ts = (base + timedelta(seconds=t_rel)).isoformat()
                w.writerow([mmsi, f"{lat:.6f}", f"{lon:.6f}", f"{sog:.2f}", ts])
                n_rows += 1
                wrote_any = True
                if sog > sog_max:
                    sog_max = sog
            if wrote_any:
                n_tracks += 1

    rel = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"  Ushant -> {rel}")
    print(f"  tracks={n_tracks:,}  rows={n_rows:,}  max_SOG={sog_max:.1f}kn"
          + (f"  dropped_by_box={n_dropped_box:,}" if box else ""))
    print("  schema: MMSI,LAT,LON,SOG,BaseDateTime (ISO-8601) | VesselType+Status omitted (not in source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
