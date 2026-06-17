"""Deterministic generator for fixtures/smoke_25.jsonl (synthetic, unclassified).

25 lines: 17 clean + 1 clean-but-stale (WARN) + 4 peril (BREACH each) + 3 malformed.
Expected after the gate: 25 observations, 4 BREACH + 4 WARN (1 stale + 3 malformed),
verify PASS. Seeded; identical bytes every run (replay fidelity).
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)
HERE = Path(__file__).resolve().parent
T0 = datetime(2026, 6, 17, 17, 0, 0, tzinfo=timezone.utc)
BOX = {"lat_min": 32.55, "lat_max": 32.95, "lon_min": -117.45, "lon_max": -116.95}
CLASSES = ["vehicle", "person", "boat", "aircraft", "structure"]


def base(i: int, model: str) -> dict:
    t = T0 + timedelta(seconds=8 * i)
    return {
        "obs_id": f"obs-{i:03d}",
        "ts_emitted": t.isoformat(),
        "ts_observed_offset_ms": 40 + random.randint(0, 60),
        "source_vendor": "vendor-a" if model != "detector-v3" else "vendor-c",
        "source_model_id": model,
        "decision_type": "detection",
        "payload": {
            "class": random.choice(CLASSES),
            "target_id": f"tgt-{random.randint(100, 999)}",
        },
        "confidence": round(random.uniform(0.74, 0.97), 2),
        "geo": {
            "lat": round(random.uniform(BOX["lat_min"] + 0.02, BOX["lat_max"] - 0.02), 5),
            "lon": round(random.uniform(BOX["lon_min"] + 0.02, BOX["lon_max"] - 0.02), 5),
            "ce": round(random.uniform(5, 40), 1),
        },
        "classification": "UNCLASSIFIED",
        "ddil_profile": "nominal",
        "upstream_provenance": [f"frame-sha256:{random.getrandbits(64):016x}"],
        "model_fingerprint": {"detector-v1": "fp-v1", "detector-v2": "fp-v2", "detector-v3": None}[model],
    }


lines: list[str] = []

# 17 clean (v1/v2 alternating)
for i in range(17):
    lines.append(json.dumps(base(i, "detector-v1" if i % 2 == 0 else "detector-v2")))

# 1 clean-but-stale -> WARN stale_decision
stale = base(17, "detector-v1")
stale["stale"] = (T0 + timedelta(seconds=8 * 17) - timedelta(seconds=30)).isoformat()
lines.append(json.dumps(stale))

# peril 1: confidence under floor (drifted v3 emitting junk-confidence) -> BREACH confidence_floor
p1 = base(18, "detector-v3")
p1["confidence"] = 0.55
lines.append(json.dumps(p1))

# peril 2: geofence walk-out during link-loss -> BREACH geofence (satcom_denied IS authorized)
p2 = base(19, "detector-v3")
p2["geo"] = {"lat": 33.21, "lon": -117.80, "ce": 25.0}
p2["ddil_profile"] = "satcom_denied"
lines.append(json.dumps(p2))

# peril 3: forbidden-class adjacency (protected object inside sensor CE) -> BREACH
p3 = base(20, "detector-v2")
p3["payload"]["adjacent_classes"] = ["school"]
lines.append(json.dumps(p3))

# peril 4: imagery-derived decision with no provenance -> BREACH provenance_missing
p4 = base(21, "detector-v3")
p4["upstream_provenance"] = []
lines.append(json.dumps(p4))

# 3 malformed (observed and chained as garbage; WARN each)
lines.append('{"obs_id": "obs-022", "ts_emitted": NOT_JSON')
lines.append("totally not json at all")
lines.append('{"obs_id": "obs-024"}')  # parseable JSON but missing required fields

(HERE / "smoke_25.jsonl").write_text("\n".join(lines) + "\n")
print(f"wrote {len(lines)} lines -> {HERE / 'smoke_25.jsonl'}")
