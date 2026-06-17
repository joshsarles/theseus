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


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    print("THESEUS demo · STEP 1 — Stage Operational Data")
    rows = _fetch_real()
    source = "UCI #316 (real naval gas-turbine CBM)"
    if rows is None:
        if STAGED.exists():
            print(f"  using cached staged data at {STAGED.relative_to(HERE.parent)}")
            data_bytes = STAGED.read_bytes()
            sha = hashlib.sha256(data_bytes).hexdigest()
            n = sum(1 for _ in io.StringIO(data_bytes.decode())) - 1
            seal(RECORD, "data_staged", "staged.csv",
                 {"source": "cache", "rows": n, "sha256": sha, "target": TARGET})
            print(f"  sealed data_staged · rows={n} · sha256={sha[:12]}…")
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
    seal(RECORD, "data_staged", "staged.csv",
         {"source": source, "rows": len(rows), "features": fields, "sha256": sha, "target": TARGET})
    print(f"  source: {source}")
    print(f"  staged {len(rows)} rows -> {STAGED.relative_to(HERE.parent)}")
    print(f"  sealed data_staged · sha256={sha[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
