"""Generate additional synthetic UUV sensor data for uuv2 (pi2 / CONTACTS).

Fits the per-sensor NORMAL distribution from the seed file (uuv1-sensors-anom.json) and
samples N new normal records from it, then injects anomalies with the observed signatures
(turbidity / pressure / sonar-return spikes, temp/salinity excursions, acoustic dropout).
Anomalies are tagged `-ANOMALY` in record_id (the eval/label convention). The seed records
are kept, so the output is the seed + N synthetic = a larger uuv2 training set.

    python3 serve/receiver/gen_synthetic_sensors.py [N_NEW]      # default 500
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from statistics import mean, pstdev

HERE = Path(__file__).resolve().parent
SEED = HERE / "data" / "uuv1-sensors-anom.json"
OUT = HERE / "data" / "uuv2-sensors-anom.json"
N_NEW = int(sys.argv[1]) if len(sys.argv) > 1 else 500
ANOM_RATE = 0.22
SEED_RNG = 1234
FIELDS = ["water_temp_c", "salinity_ppt", "turbidity_ntu", "sonar_range_m",
          "sonar_bearing_deg", "sonar_return_db", "pressure_bar"]


def fit_normal(records: list[dict]) -> dict:
    norm = [r for r in records if "ANOMALY" not in str(r.get("record_id", "")).upper()]
    stats = {}
    for f in FIELDS:
        vals = [float(r[f]) for r in norm if f in r and isinstance(r[f], (int, float))]
        m = mean(vals); s = pstdev(vals) or abs(m) * 0.05 or 1.0
        stats[f] = (m, s, min(vals), max(vals))
    return stats


def gen_normal(rng: random.Random, stats: dict) -> dict:
    rec = {}
    for f in FIELDS:
        m, s, lo, hi = stats[f]
        rec[f] = round(max(lo - s, min(hi + s, rng.gauss(m, s))), 3)  # clamp near observed range
    rec["acoustic_modem_status"] = 1
    return rec


def gen_anomaly(rng: random.Random, stats: dict) -> dict:
    rec = gen_normal(rng, stats)
    signatures = [
        ("turbidity_ntu", lambda: rng.uniform(50, 150)),       # sediment plume / fouling
        ("pressure_bar", lambda: rng.uniform(30, 55)),         # depth/hull anomaly
        ("sonar_return_db", lambda: rng.uniform(-30, -10)),    # unexpected strong return
        ("water_temp_c", lambda: rng.choice([rng.uniform(2, 8), rng.uniform(28, 35)])),
        ("salinity_ppt", lambda: rng.uniform(20, 28)),         # freshwater intrusion
    ]
    for f, fn in rng.sample(signatures, rng.randint(1, 2)):
        rec[f] = round(fn(), 3)
    if rng.random() < 0.4:
        rec["acoustic_modem_status"] = 0                       # comms dropout
    return rec


def main() -> int:
    seed = json.loads(SEED.read_text())
    stats = fit_normal(seed)
    rng = random.Random(SEED_RNG)
    new = []
    for i in range(N_NEW):
        is_anom = rng.random() < ANOM_RATE
        rec = gen_anomaly(rng, stats) if is_anom else gen_normal(rng, stats)
        rec["record_id"] = f"synth-{i:04d}-ANOMALY" if is_anom else f"synth-{i:04d}"
        rec["vehicle_id"] = "UUV-002"
        rec["vehicle_type"] = "UUV"
        rec["timestamp_utc"] = f"2026-06-18T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z"
        new.append(rec)
    combined = seed + new
    OUT.write_text(json.dumps(combined, indent=2))
    n_anom = sum(1 for r in combined if "ANOMALY" in str(r["record_id"]).upper())
    print(f"  wrote {len(combined)} records ({len(seed)} seed + {len(new)} synthetic) — "
          f"{n_anom} anomalies ({100*n_anom/len(combined):.0f}%) → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
