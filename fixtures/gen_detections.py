"""Generate a deterministic, synthetic, unclassified detection stream for the PED demo.

NOT real imagery. NOT real geography. A reproducible stand-in so the correlation engine
(referee/ped_demo.py) has something to fuse into a living target picture. Stated out loud
in the demo every time.

Ground truth (the engine never sees `truth_id` — it's here only so the test can check the
engine recovered the right picture):
  - a 2-vehicle convoy moving NE in formation (two tracks, one formation),
  - one stationary vehicle at a motor pool (one track, its own formation),
  - a little sensor noise (detections that should NOT form a persistent track).
Three sensors (EO / SAR / FMV) each glimpse the objects with gaps, at 60s cadence.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "detections.jsonl"

SEED = 20260616  # fixed: same stream every run (no wall-clock, no live randomness)
STEPS = 6
STEP_SECONDS = 60
SENSORS = ("EO", "SAR", "FMV")
T0 = "2026-06-16T17:00:00Z"  # synthetic anchor; emitted-vs-observed offsets are per-sensor

# Ground-truth objects in synthetic decimal degrees (NOT a real place).
# Convoy = two vehicles abreast (~560m apart), moving NE at the same velocity. Wide enough
# that the association gate never bridges them; close enough that they cluster as one formation.
_CONVOY = (
    {"truth_id": "veh-A", "lat": 33.1000, "lon": 44.2000},
    {"truth_id": "veh-B", "lat": 33.1000, "lon": 44.2060},
)
_CONVOY_V = (0.0008, 0.0006)  # per-step displacement (lat, lon), heading NE, both vehicles
_STATIONARY = {"truth_id": "veh-C", "lat": 33.1100, "lon": 44.2200}
# Clutter lives well outside the convoy corridor and the watch box, so it cannot bridge tracks.
_CLUTTER_CENTER = (33.0820, 44.1780)

# Per-sensor processing latency: ts_observed (when the photon landed) precedes ts_emitted
# (when the vendor model finished). Bi-temporal memory keeps both.
_SENSOR_LATENCY_S = {"EO": 5, "SAR": 12, "FMV": 3}
# FMV is a persistent-stare sensor: it sees every object every step (no track gaps).
# EO/SAR are revisit sensors: probabilistic glimpses that thicken the track.
_PERSISTENT_SENSOR = "FMV"
_SENSOR_PDET = {"EO": 0.7, "SAR": 0.6, "FMV": 1.0}


def _iso(base_iso: str, plus_seconds: int) -> str:
    # stdlib-only, no wall clock: parse the fixed anchor and add seconds.
    from datetime import datetime, timedelta, timezone

    base = datetime.fromisoformat(base_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    return (base + timedelta(seconds=plus_seconds)).isoformat().replace("+00:00", "Z")


def main() -> None:
    rng = random.Random(SEED)
    rows: list[dict] = []
    det_n = 0

    def emit(truth_id: str, lat: float, lon: float, sensor: str, step: int) -> None:
        nonlocal det_n
        noise = lambda: rng.gauss(0.0, 0.00006)  # ~7m positional noise
        obs_s = step * STEP_SECONDS
        rows.append(
            {
                "det_id": f"det-{det_n:03d}",
                "sensor": sensor,
                "ts_observed": _iso(T0, obs_s),
                "ts_emitted": _iso(T0, obs_s + _SENSOR_LATENCY_S[sensor]),
                "lat": round(lat + noise(), 6),
                "lon": round(lon + noise(), 6),
                "confidence": round(rng.uniform(0.62, 0.95), 2),
                "classification": "UNCLASSIFIED",
                "truth_id": truth_id,  # fixture-only; the engine ignores this
            }
        )
        det_n += 1

    for step in range(STEPS):
        # convoy advances in formation
        for base in _CONVOY:
            lat = base["lat"] + _CONVOY_V[0] * step
            lon = base["lon"] + _CONVOY_V[1] * step
            for sensor in SENSORS:
                if rng.random() < _SENSOR_PDET[sensor]:
                    emit(base["truth_id"], lat, lon, sensor, step)
        # stationary vehicle
        for sensor in SENSORS:
            if rng.random() < _SENSOR_PDET[sensor]:
                emit(_STATIONARY["truth_id"], _STATIONARY["lat"], _STATIONARY["lon"], sensor, step)
        # occasional sensor noise, parked far outside the corridor (should not persist into a track)
        if rng.random() < 0.5:
            emit("noise", _CLUTTER_CENTER[0] + rng.uniform(-0.01, 0.01),
                 _CLUTTER_CENTER[1] + rng.uniform(-0.01, 0.01), rng.choice(SENSORS), step)

    # deterministic order: by ts_observed then det_id (the stream as it would arrive)
    rows.sort(key=lambda r: (r["ts_observed"], r["det_id"]))
    OUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"wrote {len(rows)} synthetic detections -> {OUT}")


if __name__ == "__main__":
    main()
