#!/usr/bin/env python3
"""THESEUS demo — STEP 1: Stage Operational Data.

Production: a snapshot of ship HM&E telemetry, or a live SDR AIS/ADS-B capture
on a Pi (the airgapped "no historical DB" cold-start money shot).
Demo: the REAL UCI #316 "Condition-Based Maintenance of Naval Propulsion Plants"
dataset (real frigate gas-turbine decay data; CC BY 4.0). See
docs/research/datasets/D_SHIP_MACHINERY_CBM_REPORT.md.

Stages to demo/data/staged.csv and seals a `data_staged` leaf (sha256 + rows)
into the tamper-evident record. Run ONCE online to cache the real data; after
that it works fully offline (objective #4: pre-stage, no sneakernet).
"""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from _record import seal

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RECORD = HERE / "out" / "record"
STAGED = DATA / "staged.csv"

# UCI #316 target we predict in the demo: GT compressor decay state coefficient.
TARGET = "gt_compressor_decay"

# ── Contact-positions cache (cold-start fix, DAY2_PREP risk #9) ───────────────
# The CONTACTS beat needs lat/lon for the handful of FLAGGED MMSIs to drop pins on
# the CIC map. The source is the real ~773MB MarineCadastre AIS CSV. Scanning it
# synchronously on the first /api/state took multiple seconds (full file = 7.3M
# rows ≈ 5.5s) → the UI's first poll timed out → it latched to the mock fixture →
# an ugly, dishonest cold-open. Fix: pre-compute the last-known (lat,lon) for ONLY
# the flagged MMSIs into a tiny JSON ONCE at stage time, so a cold /api/state just
# loads ~50 entries (<1s) and never has to touch the big CSV on the request path.
# api.py imports these symbols so the cache schema + the fallback scan are one
# source of truth (no drift between the writer here and the reader/fallback there).
AIS_CSV = HERE.parent / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
POSITIONS_CACHE = DATA / "positions.json"
# MarineCadastre AIS schema (header row 0): MMSI=col0, LAT=col2, LON=col3.
_AIS_MMSI_COL, _AIS_LAT_COL, _AIS_LON_COL = 0, 2, 3


def flagged_mmsis(record_dir: Path) -> set[str]:
    """The MMSIs the AIS-PoL cell sealed as anomalies — exactly the contacts the CIC
    map must pin. Read straight from the tamper-evident record (the `ais_anomaly`
    leaves), so the cache covers precisely what /api/state will render, no more.

    Stdlib-only, reads chain.jsonl directly (the record is the authority); returns an
    empty set if there is no record yet (then there is nothing to pre-compute)."""
    import base64 as _b64
    import json as _json

    out: set[str] = set()
    cp = record_dir / "chain.jsonl"
    if not cp.exists():
        return out
    for line in cp.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = _json.loads(line)
            if row.get("kind") != "ais_anomaly":
                continue
            data = _json.loads(_b64.b64decode(row["record_b64"]))
            mmsi = data.get("mmsi")
            if mmsi is not None:
                out.add(str(mmsi))
        except Exception:
            continue
    return out


def scan_positions(mmsis: set[str], csv_path: Path = AIS_CSV) -> dict[str, list]:
    """Last-known (lat,lon) for `mmsis` from the real AIS CSV — one full pass.

    Returns {mmsi: [lat, lon]} for every requested MMSI found in the file. Scans the
    WHOLE file (last fix wins) so a contact whose only fixes are late in the day still
    gets a correct pin — the previous in-API scan capped at 1.5M rows and silently
    dropped those. Early-exits once every requested MMSI has a position, so the common
    case (a few flagged contacts that appear early) returns fast. Pure stdlib."""
    found: dict[str, list] = {}
    if not mmsis or not csv_path.exists():
        return found
    want = set(mmsis)
    with csv_path.open() as f:
        r = csv.reader(f)
        next(r, None)  # header
        for row in r:
            try:
                m = row[_AIS_MMSI_COL]
                if m in want:
                    found[m] = [round(float(row[_AIS_LAT_COL]), 5),
                                round(float(row[_AIS_LON_COL]), 5)]
                    if len(found) == len(want):
                        break  # have every requested contact — stop scanning
            except (IndexError, ValueError):
                continue
    return found


def precompute_positions(record_dir: Path = RECORD,
                         csv_path: Path = AIS_CSV,
                         out_path: Path = POSITIONS_CACHE) -> dict:
    """Build the tiny contact-positions cache for the flagged MMSIs and write it to
    `out_path` as JSON. Idempotent; safe to run every stage. Returns a small summary.

    This is the cold-start fix: do the one expensive CSV pass HERE (stage time, off
    the demo's critical path), so /api/state never scans the big file on a request."""
    import json as _json

    mmsis = flagged_mmsis(record_dir)
    positions = scan_positions(mmsis, csv_path) if mmsis else {}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "theseus/contact-positions/v1",
        "source": str(csv_path.name),
        "csv_present": csv_path.exists(),
        "flagged_count": len(mmsis),
        "resolved_count": len(positions),
        "positions": positions,  # {mmsi: [lat, lon]}
    }
    out_path.write_text(_json.dumps(payload, indent=2))
    return payload


def _fetch_real() -> list[dict] | None:
    """Real UCI #316 via ucimlrepo (needs network on first call; then cache)."""
    try:
        from ucimlrepo import fetch_ucirepo
    except ImportError:
        return None
    try:
        ds = fetch_ucirepo(id=316)
    except Exception as e:  # offline / fetch error
        print(f"  (ucimlrepo fetch failed: {e})")
        return None
    X = ds.data.features
    y = ds.data.targets
    cols = list(X.columns)
    target_col = list(y.columns)[0]  # GT Compressor decay state coefficient
    rows = []
    for i in range(len(X)):
        row = {c.strip().lower().replace(" ", "_")[:24]: float(X.iloc[i][c]) for c in cols}
        row[TARGET] = float(y.iloc[i][target_col])
        rows.append(row)
    return rows


def _placeholder() -> list[dict]:
    """Physics-shaped PLACEHOLDER so the loop runs offline before real data is cached.
    Decay coefficient ~ f(fouling proxy) + noise. CLEARLY not real — replace ASAP."""
    import math
    import random

    rng = random.Random(316)
    rows = []
    for _ in range(600):
        speed = rng.uniform(3, 27)                  # ship speed (knots)
        shaft_rpm = 40 * speed + rng.uniform(-30, 30)
        comp_out_temp = 600 + 6 * speed + rng.uniform(-20, 20)
        comp_out_press = 5 + 0.4 * speed + rng.uniform(-0.3, 0.3)
        fuel_flow = 0.2 + 0.05 * speed + rng.uniform(-0.02, 0.02)
        # decay coefficient in UCI's real range ~0.95 (fouled) .. 1.0 (clean)
        fouling = 0.5 * (comp_out_temp - 600) / 200 + 0.5 * (fuel_flow - 0.2) / 1.3
        decay = 1.0 - 0.05 * max(0.0, min(1.0, fouling)) + rng.gauss(0, 0.004)
        rows.append({
            "ship_speed": round(speed, 3),
            "gt_shaft_rpm": round(shaft_rpm, 2),
            "comp_outlet_temp": round(comp_out_temp, 2),
            "comp_outlet_press": round(comp_out_press, 3),
            "fuel_flow": round(fuel_flow, 4),
            TARGET: round(max(0.95, min(1.0, decay)), 5),
        })
    return rows


def _emit_positions(record_dir: Path, csv_path: Path, out_path: Path) -> None:
    """Build + report the flagged-contact positions cache (cold-start fix). Best-effort:
    a failure here must never break staging — /api/state still has its lazy CSV fallback."""
    try:
        summary = precompute_positions(record_dir, csv_path, out_path)
        rel = out_path.relative_to(HERE.parent) if out_path.is_relative_to(HERE.parent) else out_path
        print(f"  positions cache → {rel} · flagged={summary['flagged_count']} "
              f"resolved={summary['resolved_count']} (cold /api/state stays <1s)")
    except Exception as e:  # pragma: no cover - defensive; cache is an optimization, not a gate
        print(f"  (positions pre-compute skipped: {e}; /api/state will lazy-scan as fallback)")


def main() -> int:
    import argparse
    import shutil
    ap = argparse.ArgumentParser(description="Stage operational data for the loop.")
    ap.add_argument("--input", help="pre-normalized CSV (last column = target) from an ingest/ adapter")
    ap.add_argument("--positions-only", action="store_true",
                    help="ONLY (re)build the flagged-contact positions cache from the record + AIS CSV "
                         "(run AFTER demo/ais_pol.py has sealed the ais_anomaly leaves). The cold-start fix.")
    ap.add_argument("--record", default=str(RECORD),
                    help="record dir to read flagged MMSIs from (default: demo/out/record)")
    ap.add_argument("--ais-csv", default=str(AIS_CSV), help="MarineCadastre AIS CSV to scan for positions")
    ap.add_argument("--positions-out", default=str(POSITIONS_CACHE),
                    help="where to write the tiny positions cache JSON")
    a = ap.parse_args()
    record_dir = Path(a.record)
    ais_csv = Path(a.ais_csv)
    pos_out = Path(a.positions_out)
    DATA.mkdir(parents=True, exist_ok=True)

    # Cold-start fix entry point: just (re)build the positions cache and exit. Used by the
    # demo flow AFTER ais_pol.py seals the flagged contacts (they don't exist at stage time).
    if a.positions_only:
        print("THESEUS demo · positions cache — pre-compute flagged-contact lat/lon")
        _emit_positions(record_dir, ais_csv, pos_out)
        return 0

    print("THESEUS demo · STEP 1 — Stage Operational Data")

    # Plug-in path: an ingest/ adapter (THESEUS lane) already normalized a dataset to the
    # loop's data contract — copy it in and seal it. (Contract: numeric features + last col = target.)
    if a.input:
        src = Path(a.input)
        if not src.exists():
            print(f"  --input not found: {src}")
            return 1
        shutil.copyfile(src, STAGED)
        sha = hashlib.sha256(STAGED.read_bytes()).hexdigest()
        n = sum(1 for _ in STAGED.open()) - 1
        tgt = next(csv.reader(STAGED.open()))[-1]       # contract: last column = target
        (DATA / ".target").write_text(tgt)
        seal(RECORD, "data_staged", "staged.csv",
             {"source": f"ingest:{src.name}", "rows": n, "sha256": sha, "target": tgt})
        print(f"  staged from {src} · rows={n} · target={tgt} · sha256={sha[:12]}…")
        _emit_positions(record_dir, ais_csv, pos_out)
        return 0

    rows = _fetch_real()
    source = "UCI #316 (real naval gas-turbine CBM)"
    if rows is None:
        if STAGED.exists():
            print(f"  using cached staged data at {STAGED.relative_to(HERE.parent)}")
            data_bytes = STAGED.read_bytes()
            sha = hashlib.sha256(data_bytes).hexdigest()
            n = sum(1 for _ in io.StringIO(data_bytes.decode())) - 1
            tgt = next(csv.reader(io.StringIO(data_bytes.decode())))[-1]
            (DATA / ".target").write_text(tgt)
            seal(RECORD, "data_staged", "staged.csv",
                 {"source": "cache", "rows": n, "sha256": sha, "target": tgt})
            print(f"  sealed data_staged · rows={n} · target={tgt} · sha256={sha[:12]}…")
            _emit_positions(record_dir, ais_csv, pos_out)
            return 0
        print("  ⚠ PLACEHOLDER DATA (offline + no cache) — NOT REAL.")
        print("    Run online once with `pip install ucimlrepo` to cache real UCI #316.")
        rows = _placeholder()
        source = "PLACEHOLDER (physics-shaped, NOT REAL — replace with UCI #316)"

    fields = list(rows[0].keys())
    with STAGED.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    sha = hashlib.sha256(STAGED.read_bytes()).hexdigest()
    (DATA / ".target").write_text(fields[-1])
    seal(RECORD, "data_staged", "staged.csv",
         {"source": source, "rows": len(rows), "features": fields, "sha256": sha, "target": fields[-1]})
    print(f"  source: {source}")
    print(f"  staged {len(rows)} rows -> {STAGED.relative_to(HERE.parent)} · target={fields[-1]}")
    print(f"  sealed data_staged · sha256={sha[:12]}…")
    _emit_positions(record_dir, ais_csv, pos_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
