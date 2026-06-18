import json
from pathlib import Path

SENSORS_FILE = Path("uuv1-sensors-anom.json")
TELEMETRY_FILE = Path("uuv1-telemetry-anom.json")
C2_FILE = Path("../data/UUV1-c2.json")

OUT_C2_ANOM = Path("uuv1-c2-anom.json")
OUT_ALL_ANOM = Path("uuv1-all-anom.json")
OUT_FEATURES = Path("features.json")

FEATURES = [
    "sequence_num", "payload_bytes", "latency_ms",
    "water_temp_c", "salinity_ppt", "turbidity_ntu",
    "sonar_range_m", "sonar_bearing_deg", "sonar_return_db", "pressure_bar",
    "latitude_deg", "longitude_deg", "speed_knots", "heading_deg",
    "depth_m", "altitude_asl_m", "roll_deg", "pitch_deg",
    "battery_pct", "signal_strength_dbm", "hdop",
]

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def keep_numeric(record):
    return {k: record.get(k) for k in FEATURES if k in record}

sensors = load(SENSORS_FILE)
telemetry = load(TELEMETRY_FILE)
c2 = load(C2_FILE)

n = min(len(sensors), len(telemetry), len(c2))

# Make C2 anomaly stream by copying C2 and injecting obvious latency/payload anomalies.
c2_anom = c2[:n]
for i, row in enumerate(c2_anom):
    if i % 12 == 0:
        row["latency_ms"] = max(float(row.get("latency_ms", 0)), 2500.0)
        row["payload_bytes"] = max(int(row.get("payload_bytes", 0)), 4000)

OUT_C2_ANOM.write_text(json.dumps(c2_anom, indent=2), encoding="utf-8")

merged = []
for i in range(n):
    row = {}

    row.update(keep_numeric(c2_anom[i]))
    row.update(keep_numeric(sensors[i]))
    row.update(keep_numeric(telemetry[i]))

    row["record_id"] = sensors[i].get("record_id", f"stream-{i}")
    row["vehicle_id"] = sensors[i].get("vehicle_id", "UUV-001")
    row["vehicle_type"] = sensors[i].get("vehicle_type", "UUV")
    row["timestamp_utc"] = sensors[i].get("timestamp_utc")

    merged.append(row)

OUT_ALL_ANOM.write_text(json.dumps(merged, indent=2), encoding="utf-8")

OUT_FEATURES.write_text(
    json.dumps({"all": FEATURES}, indent=2),
    encoding="utf-8"
)

print(f"Wrote {OUT_C2_ANOM} with {len(c2_anom)} records")
print(f"Wrote {OUT_ALL_ANOM} with {len(merged)} merged records")
print(f"Wrote {OUT_FEATURES} with topic key 'all'")