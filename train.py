import json
import glob
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import mlflow
import mlflow.sklearn
import os

# --- Config ---
DATA_FOLDER = "data/"
CONTAMINATION = 0.05
RANDOM_STATE = 42

# Numeric cols to use from each data type
SENSOR_COLS    = ["water_temp_c", "salinity_ppt", "turbidity_ntu", "radar_range_m",
                  "radar_bearing_deg", "ais_contacts", "wind_speed_knots",
                  "wind_dir_deg", "wave_height_m"]

TELEMETRY_COLS = ["latitude_deg", "longitude_deg", "speed_knots", "heading_deg",
                  "depth_m", "altitude_asl_m", "roll_deg", "pitch_deg",
                  "battery_pct", "signal_strength_dbm", "hdop"]

C2_COLS        = ["sequence_num", "payload_bytes", "latency_ms"]

CONTEXT_COLS   = ["record_id", "vehicle_id", "vehicle_type", "timestamp_utc"]

mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("UAV Anomaly Detection")


# --- Loaders ---
def load_json(pattern):
    files = glob.glob(pattern)
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.DataFrame(json.load(open(f))) for f in files], ignore_index=True)


def build_dataset(prefix):
    c2  = load_json(f"{DATA_FOLDER}{prefix}*c2.json")
    sen = load_json(f"{DATA_FOLDER}{prefix}*sensors.json")
    tel = load_json(f"{DATA_FOLDER}{prefix}*telemetry.json")

    frames = []
    for df, cols in [(c2, C2_COLS), (sen, SENSOR_COLS), (tel, TELEMETRY_COLS)]:
        if df.empty:
            continue
        keep = CONTEXT_COLS + [c for c in cols if c in df.columns]
        frames.append(df[keep])

    if not frames:
        return pd.DataFrame()

    # Merge all three on context cols, outer join to keep all rows
    merged = frames[0]
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on=CONTEXT_COLS, how="outer")

    return merged


def train_and_log(df, run_name, feature_cols):
    """Train IsolationForest on df and log everything to MLflow."""
    df_model = df[feature_cols].copy()
    df_model = df_model.fillna(df_model.median(numeric_only=True))

    if df_model.shape[0] < 2:
        print(f"  Skipping {run_name} — not enough rows ({df_model.shape[0]})")
        return

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_model)

    with mlflow.start_run(run_name=run_name):
        # Log dataset
        dataset = mlflow.data.from_pandas(df_model, name=run_name)
        mlflow.log_input(dataset, context="training")

        # Log params
        mlflow.log_param("contamination", CONTAMINATION)
        mlflow.log_param("n_estimators", 100)
        mlflow.log_param("n_rows", df_model.shape[0])
        mlflow.log_param("n_features", df_model.shape[1])
        mlflow.log_param("features", feature_cols)

        # Train
        model = IsolationForest(
            contamination=CONTAMINATION,
            n_estimators=100,
            random_state=RANDOM_STATE
        )
        model.fit(X_scaled)

        predictions = model.predict(X_scaled)
        scores      = model.decision_function(X_scaled)

        n_anomalies = (predictions == -1).sum()
        anomaly_pct = n_anomalies / len(predictions) * 100

        mlflow.log_metric("n_anomalies", int(n_anomalies))
        mlflow.log_metric("anomaly_pct", round(anomaly_pct, 2))
        mlflow.log_metric("mean_anomaly_score", round(scores.mean(), 4))

        # Save anomalies CSV
        df_out = df[CONTEXT_COLS].copy() if all(c in df.columns for c in CONTEXT_COLS) else pd.DataFrame()
        df_out["anomaly_score"] = scores
        df_out["is_anomaly"]    = predictions == -1
        df_out = df_out.sort_values("anomaly_score")

        out_path = f"anomalies_{run_name.replace(' ', '_')}.csv"
        df_out.to_csv(out_path, index=False)
        mlflow.log_artifact(out_path)
        os.remove(out_path)  # clean up local after logging

        # Save model
        mlflow.sklearn.log_model(model, f"model-{run_name.replace(' ', '_')}")

        print(f"  {run_name}: {n_anomalies} anomalies ({anomaly_pct:.1f}%) from {df_model.shape[0]} rows")


# --- All feature cols combined ---
ALL_FEATURE_COLS = C2_COLS + SENSOR_COLS + TELEMETRY_COLS


# --- Main ---
print("=== Fleet-wide models ===")
fleet_df = build_dataset("fleet")
if not fleet_df.empty:
    feature_cols = [c for c in ALL_FEATURE_COLS if c in fleet_df.columns]
    train_and_log(fleet_df, "fleet-all-sensors", feature_cols)
    train_and_log(fleet_df, "fleet-sensors-only", [c for c in SENSOR_COLS    if c in fleet_df.columns])
    train_and_log(fleet_df, "fleet-telemetry-only", [c for c in TELEMETRY_COLS if c in fleet_df.columns])
    train_and_log(fleet_df, "fleet-c2-only", [c for c in C2_COLS           if c in fleet_df.columns])

print("\n=== Per-vehicle models ===")
# Auto-detect vehicle prefixes from filenames
all_files   = glob.glob(f"{DATA_FOLDER}*.json")
prefixes    = set()
for f in all_files:
    name = os.path.basename(f)
for suffix in ["-c2.json", "-sensors.json", "-telemetry.json", "_c2.json", "_sensors.json", "_telemetry.json"]:
    if name.endswith(suffix):
        prefixes.add(name[:-len(suffix)])

vehicle_prefixes = [p for p in prefixes if p != "fleet"]

for prefix in sorted(vehicle_prefixes):
    print(f"\n-- {prefix} --")
    vehicle_df = build_dataset(prefix)
    if vehicle_df.empty:
        print(f"  No data found for {prefix}")
        continue
    feature_cols = [c for c in ALL_FEATURE_COLS if c in vehicle_df.columns]
    train_and_log(vehicle_df, f"{prefix}-all", feature_cols)
    tel_cols = [c for c in TELEMETRY_COLS if c in vehicle_df.columns]
    if tel_cols:
        train_and_log(vehicle_df, f"{prefix}-telemetry", tel_cols)
    sen_cols = [c for c in SENSOR_COLS if c in vehicle_df.columns]
    if sen_cols:
        train_and_log(vehicle_df, f"{prefix}-sensors", sen_cols)
    c2_cols = [c for c in C2_COLS if c in vehicle_df.columns]
    if c2_cols:
        train_and_log(vehicle_df, f"{prefix}-c2", c2_cols)
print("\nDone! View results at http://localhost:5000")