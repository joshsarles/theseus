"""Generate synthetic UUV sensor data for uuv2 (pi2 / CONTACTS) — batch or live stream.

Fits the per-sensor NORMAL distribution from the seed file (uuv1-sensors-anom.json) and
samples records from it, injecting anomalies with the observed signatures (turbidity /
pressure / sonar-return spikes, temp/salinity excursions, acoustic dropout). Anomalies are
tagged `-ANOMALY` in record_id (the eval/label convention).

Two modes:
  • BATCH (default): write seed + N synthetic records to a training file.
      python3 serve/receiver/gen_synthetic_sensors.py --n 500
  • STREAM: continuously emit ONE record every INTERVAL seconds, POSTed to the receiver's
    /stream-item endpoint (a live sensor feed the receiver scores in real time).
      python3 serve/receiver/gen_synthetic_sensors.py --stream            # 1 record / 30s → localhost:54321
      python3 serve/receiver/gen_synthetic_sensors.py --stream --interval 30 --url http://localhost:54321
"""
from __future__ import annotations

import argparse
import json
import random
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

HERE = Path(__file__).resolve().parent
SEED = HERE / "data" / "uuv1-sensors-anom.json"
OUT = HERE / "data" / "uuv2-sensors-anom.json"
ANOM_RATE = 0.22
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


def make_record(rng: random.Random, stats: dict, rid: str, is_anom: bool, ts: str) -> dict:
    rec = gen_anomaly(rng, stats) if is_anom else gen_normal(rng, stats)
    rec["record_id"] = rid + ("-ANOMALY" if is_anom else "")
    rec["vehicle_id"] = "UUV-002"
    rec["vehicle_type"] = "UUV"
    rec["timestamp_utc"] = ts
    return rec


def batch(n_new: int) -> int:
    seed = json.loads(SEED.read_text())
    stats = fit_normal(seed)
    rng = random.Random(1234)
    new = [make_record(rng, stats, f"synth-{i:04d}", rng.random() < ANOM_RATE,
                       f"2026-06-18T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z")
           for i in range(n_new)]
    combined = seed + new
    OUT.write_text(json.dumps(combined, indent=2))
    n_anom = sum(1 for r in combined if "ANOMALY" in str(r["record_id"]).upper())
    print(f"  wrote {len(combined)} records ({len(seed)} seed + {len(new)} synthetic) — "
          f"{n_anom} anomalies ({100 * n_anom / len(combined):.0f}%) → {OUT.name}")
    return 0


def stream(interval: float, url: str, anom_rate: float) -> int:
    stats = fit_normal(json.loads(SEED.read_text()))
    rng = random.Random()   # live feed → non-deterministic
    print(f"  streaming 1 record / {interval:g}s → {url}  (anomaly rate {anom_rate:.0%}; Ctrl-C to stop)")
    i = 0
    while True:
        is_anom = rng.random() < anom_rate
        now = datetime.now(timezone.utc)
        rec = make_record(rng, stats, f"live-{now.strftime('%Y%m%dT%H%M%S')}", is_anom,
                          now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        body = json.dumps({"topic_id": "sensors", "data": [rec]}).encode()
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                code = r.status
            print(f"  [{now.strftime('%H:%M:%S')}] sent {rec['record_id']} "
                  f"({'ANOMALY' if is_anom else 'normal'}) → {code}", flush=True)
        except Exception as e:
            print(f"  [{now.strftime('%H:%M:%S')}] send failed: {e}", flush=True)
        i += 1
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="Synthetic UUV sensor generator (batch or live stream).")
    ap.add_argument("--stream", action="store_true", help="continuously POST 1 record / --interval to the receiver")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between records in --stream (default 30)")
    ap.add_argument("--url", default="http://localhost:54321/stream-item", help="receiver /stream-item endpoint")
    ap.add_argument("--anom-rate", type=float, default=ANOM_RATE, help="fraction of records that are anomalies")
    ap.add_argument("--n", type=int, default=500, help="batch mode: number of synthetic records to add")
    a = ap.parse_args()
    return stream(a.interval, a.url, a.anom_rate) if a.stream else batch(a.n)


if __name__ == "__main__":
    raise SystemExit(main())
