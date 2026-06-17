import json
import glob
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import mlflow
import mlflow.sklearn

# --- Config ---
DATA_FOLDER = "data/"
CONTAMINATION = 0.05
RANDOM_STATE = 42

SENSOR_COLS    = ["water_temp_c", "salinity_ppt", "turbidity_ntu", "radar_range_m",
                  "radar_bearing_deg", "ais_contacts", "wind_speed_knots",
                  "wind_dir_deg", "wave_height_m"]

TELEMETRY_COLS = ["latitude_deg", "longitude_deg", "speed_knots", "heading_deg",
                  "depth_m", "altitude_asl_m", "roll_deg", "pitch_deg",
                  "battery_pct", "signal_strength_dbm", "hdop"]

C2_COLS        = ["sequence_num", "payload_bytes", "latency_ms"]

CONTEXT_COLS   = ["record_id", "vehicle_id", "vehicle_type", "timestamp_utc"]

ALL_FEATURE_COLS = C2_COLS + SENSOR_COLS + TELEMETRY_COLS

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("UAV Anomaly Detection")


# --- Loaders ---
def load_json(pattern):
    files = glob.glob(pattern)
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.DataFrame(json.load(open(f))) for f in files], ignore_index=True)


def build_dataset(prefix):
    """Load and merge c2 + sensors + telemetry for a given prefix."""
    c2  = load_json(f"{DATA_FOLDER}{prefix}*c2.json")
    sen = load_json(f"{DATA_FOLDER}{prefix}*sensors.json")
    tel = load_json(f"{DATA_FOLDER}{prefix}*telemetry.json")

    frames = []
    for df, cols in [(c2, C2_COLS), (sen, SENSOR_COLS), (tel, TELEMETRY_COLS)]:
        if df.empty:
            continue
        keep = [c for c in CONTEXT_COLS if c in df.columns] + [c for c in cols if c in df.columns]
        frames.append(df[keep])

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for frame in frames[1:]:
        shared_cols = [c for c in CONTEXT_COLS if c in merged.columns and c in frame.columns]
        merged = pd.merge(merged, frame, on=shared_cols, how="outer")

    return merged


# --- Anomaly explainer ---
def explain_anomalies(model, df_model, df_context, feature_cols, top_n=3):
    """For each anomaly, show which features are most out of range."""
    results = []

    df_model  = df_model.select_dtypes(include=[np.number])
    means     = df_model.mean()
    stds      = df_model.std().replace(0, 1)
    z_scores  = (df_model - means) / stds

    df_model   = df_model.reset_index(drop=True)
    df_context = df_context.reset_index(drop=True)
    z_scores   = z_scores.reset_index(drop=True)

    for idx in df_model.index:
        try:
            score = model.decision_function(df_model.loc[[idx]].values)[0]
        except Exception:
            continue

        if score < 0:
            row_z        = z_scores.loc[idx].abs()
            top_features = row_z.nlargest(top_n)

            result = {
                "record_id":     df_context.loc[idx, "record_id"]     if "record_id"     in df_context.columns else idx,
                "vehicle_id":    df_context.loc[idx, "vehicle_id"]    if "vehicle_id"    in df_context.columns else "",
                "vehicle_type":  df_context.loc[idx, "vehicle_type"]  if "vehicle_type"  in df_context.columns else "",
                "timestamp_utc": df_context.loc[idx, "timestamp_utc"] if "timestamp_utc" in df_context.columns else "",
                "anomaly_score": round(score, 6),
            }

            for feat, z in top_features.items():
                result[f"flag_{feat}"]        = round(float(df_model.loc[idx, feat]), 4)
                result[f"flag_{feat}_zscore"]  = round(float(z), 2)
                result[f"flag_{feat}_mean"]    = round(float(means[feat]), 4)

            results.append(result)

    return pd.DataFrame(results) if results else pd.DataFrame()


# --- Train and log ---
def train_and_log(df, run_name, feature_cols):
    """Train IsolationForest on df and log everything to MLflow."""
    df_model = df[[c for c in feature_cols if c in df.columns]].copy()
    df_model = df_model.fillna(df_model.median(numeric_only=True))

    if df_model.shape[0] < 2:
        print(f"  Skipping {run_name} — not enough rows ({df_model.shape[0]})")
        return

    scaler  = StandardScaler()
    X_scaled = scaler.fit_transform(df_model)

    with mlflow.start_run(run_name=run_name):
        dataset = mlflow.data.from_pandas(df_model, name=run_name)
        mlflow.log_input(dataset, context="training")

        mlflow.log_param("contamination", CONTAMINATION)
        mlflow.log_param("n_estimators",  100)
        mlflow.log_param("n_rows",        df_model.shape[0])
        mlflow.log_param("n_features",    df_model.shape[1])
        mlflow.log_param("features",      list(df_model.columns))

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

        mlflow.log_metric("n_anomalies",        int(n_anomalies))
        mlflow.log_metric("anomaly_pct",         round(anomaly_pct, 2))
        mlflow.log_metric("mean_anomaly_score",  round(scores.mean(), 4))

        # Basic anomalies CSV with context
        context_cols_present = [c for c in CONTEXT_COLS if c in df.columns]
        df_results = df[context_cols_present].copy().reset_index(drop=True)
        df_results["anomaly_score"] = scores
        df_results["is_anomaly"]    = predictions == -1
        df_results = df_results.sort_values("anomaly_score")
        df_results.to_csv("anomalies_found.csv", index=False)
        mlflow.log_artifact("anomalies_found.csv")
        os.remove("anomalies_found.csv")

        # Detailed anomaly explanation — which features are causing it
        context_df      = df[context_cols_present].copy()
        anomaly_details = explain_anomalies(model, df_model, context_df, list(df_model.columns))
        if not anomaly_details.empty:
            anomaly_details = anomaly_details.sort_values("anomaly_score")
            anomaly_details.to_csv("anomaly_details.csv", index=False)
            mlflow.log_artifact("anomaly_details.csv")
            os.remove("anomaly_details.csv")

            print(f"\n  Top anomalies for {run_name}:")
            print(anomaly_details.head(5).to_string(index=False))

        mlflow.sklearn.log_model(model, f"model-{run_name.replace(' ', '_')}")

        print(f"\n  {run_name}: {n_anomalies} anomalies ({anomaly_pct:.1f}%) from {df_model.shape[0]} rows")


# --- Main ---
print("=== Fleet-wide models ===")
fleet_df = build_dataset("fleet")
if not fleet_df.empty:
    train_and_log(fleet_df, "fleet-all-sensors",    [c for c in ALL_FEATURE_COLS  if c in fleet_df.columns])
    train_and_log(fleet_df, "fleet-sensors-only",   [c for c in SENSOR_COLS       if c in fleet_df.columns])
    train_and_log(fleet_df, "fleet-telemetry-only", [c for c in TELEMETRY_COLS    if c in fleet_df.columns])
    train_and_log(fleet_df, "fleet-c2-only",        [c for c in C2_COLS           if c in fleet_df.columns])

print("\n=== Per-vehicle models ===")
all_files        = glob.glob(f"{DATA_FOLDER}*.json")
prefixes         = set()
for f in all_files:
    name = os.path.basename(f)
    for suffix in ["-c2.json", "-sensors.json", "-telemetry.json",
                   "_c2.json", "_sensors.json", "_telemetry.json"]:
        if name.endswith(suffix):
            prefixes.add(name[:-len(suffix)])

vehicle_prefixes = [p for p in prefixes if p != "fleet"]

for prefix in sorted(vehicle_prefixes):
    print(f"\n-- {prefix} --")
    vehicle_df = build_dataset(prefix)
    if vehicle_df.empty:
        print(f"  No data found for {prefix}")
        continue

    train_and_log(vehicle_df, f"{prefix}-all",       [c for c in ALL_FEATURE_COLS if c in vehicle_df.columns])

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