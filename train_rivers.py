import json
import glob
import os
import pandas as pd
import numpy as np
from river import anomaly, preprocessing
import mlflow
import pickle

# --- Config ---
DATA_FOLDER    = "data/"
CONTAMINATION  = 0.05       # approximate % of anomalies expected
N_TREES        = 25         # number of half space trees
HEIGHT         = 15         # tree height — higher = more sensitive to subtle anomalies
WINDOW_SIZE    = 250        # how many samples each tree considers at once
ANOMALY_THRESHOLD = 0.7     # score above this = anomaly (0 to 1 scale)
RANDOM_STATE   = 42

SENSOR_COLS    = ["water_temp_c", "salinity_ppt", "turbidity_ntu", "radar_range_m",
                  "radar_bearing_deg", "ais_contacts", "wind_speed_knots",
                  "wind_dir_deg", "wave_height_m"]

TELEMETRY_COLS = ["latitude_deg", "longitude_deg", "speed_knots", "heading_deg",
                  "depth_m", "altitude_asl_m", "roll_deg", "pitch_deg",
                  "battery_pct", "signal_strength_dbm", "hdop"]

C2_COLS        = ["sequence_num", "payload_bytes", "latency_ms"]

CONTEXT_COLS   = ["record_id", "vehicle_id", "vehicle_type", "timestamp_utc"]

ALL_FEATURE_COLS = C2_COLS + SENSOR_COLS + TELEMETRY_COLS

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050"))
mlflow.set_experiment("UAV Anomaly Detection - HST")


# --- Loaders ---
def load_json(pattern):
    """Load one or more JSON files matching a glob pattern into a DataFrame."""
    files = glob.glob(pattern)
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        if isinstance(data, list):
            frames.append(pd.DataFrame(data))
        elif isinstance(data, dict):
            for key in ["data", "records", "results", "items"]:
                if key in data and isinstance(data[key], list):
                    frames.append(pd.DataFrame(data[key]))
                    break
            else:
                frames.append(pd.DataFrame([data]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


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
def explain_anomalies(scores_series, df_model, df_context, top_n=3):
    """
    For each anomaly row, show which features deviate most from normal.
    scores_series: pd.Series of anomaly scores aligned with df_model index.
    """
    results  = []
    numeric  = df_model.select_dtypes(include=[np.number])
    means    = numeric.mean()
    stds     = numeric.std().replace(0, 1)
    z_scores = (numeric - means) / stds

    for idx in numeric.index:
        score = scores_series.loc[idx]
        if score >= ANOMALY_THRESHOLD:
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
                result[f"flag_{feat}"]       = round(float(numeric.loc[idx, feat]), 4)
                result[f"flag_{feat}_zscore"] = round(float(z), 2)
                result[f"flag_{feat}_mean"]   = round(float(means[feat]), 4)

            results.append(result)

    return pd.DataFrame(results) if results else pd.DataFrame()


# --- Train and log ---
def train_and_log(df, run_name, feature_cols):
    """
    Train a Half Space Trees anomaly detector on df row by row (online learning),
    log everything to MLflow, and return the trained model.

    Returns:
        model: trained River HalfSpaceTrees pipeline (or None if skipped)
    """
    feature_cols = [c for c in feature_cols if c in df.columns]
    df_model     = df[feature_cols].copy()
    df_model     = df_model.select_dtypes(include=[np.number])
    df_model     = df_model.fillna(df_model.median(numeric_only=True))

    if df_model.shape[0] < 10:
        print(f"  Skipping {run_name} — not enough rows ({df_model.shape[0]})")
        return None

    # River pipeline: standard scaler + half space trees
    model = preprocessing.StandardScaler() | anomaly.HalfSpaceTrees(
        n_trees=N_TREES,
        height=HEIGHT,
        window_size=WINDOW_SIZE,
        seed=RANDOM_STATE
    )

    scores = []

    # Online learning — feed one row at a time, just like a live sensor stream
    for _, row in df_model.iterrows():
        x     = row.to_dict()
        score = model.score_one(x)   # score before learning
        model.learn_one(x)           # update model with this reading
        scores.append(score)

    scores_series = pd.Series(scores, index=df_model.index)

    n_anomalies = (scores_series >= ANOMALY_THRESHOLD).sum()
    anomaly_pct = n_anomalies / len(scores_series) * 100
    mean_score  = scores_series.mean()

    with mlflow.start_run(run_name=run_name):
        dataset = mlflow.data.from_pandas(df_model, name=run_name)
        mlflow.log_input(dataset, context="training")

        mlflow.log_param("model_type",    "HalfSpaceTrees")
        mlflow.log_param("n_trees",       N_TREES)
        mlflow.log_param("height",        HEIGHT)
        mlflow.log_param("window_size",   WINDOW_SIZE)
        mlflow.log_param("threshold",     ANOMALY_THRESHOLD)
        mlflow.log_param("n_rows",        df_model.shape[0])
        mlflow.log_param("n_features",    df_model.shape[1])
        mlflow.log_param("features",      list(df_model.columns))

        mlflow.log_metric("n_anomalies",       int(n_anomalies))
        mlflow.log_metric("anomaly_pct",        round(anomaly_pct, 2))
        mlflow.log_metric("mean_anomaly_score", round(mean_score, 4))

        # Basic anomalies CSV
        context_cols_present = [c for c in CONTEXT_COLS if c in df.columns]
        df_results = df[context_cols_present].copy().reset_index(drop=True)
        df_results["anomaly_score"] = scores_series.values
        df_results["is_anomaly"]    = scores_series.values >= ANOMALY_THRESHOLD
        df_results = df_results.sort_values("anomaly_score", ascending=False)
        df_results.to_csv("anomalies_found.csv", index=False)
        mlflow.log_artifact("anomalies_found.csv")
        os.remove("anomalies_found.csv")

        # Detailed feature explanation for anomalies
        context_df      = df[context_cols_present].copy().reset_index(drop=True)
        anomaly_details = explain_anomalies(
            scores_series.reset_index(drop=True),
            df_model.reset_index(drop=True),
            context_df
        )
        if not anomaly_details.empty:
            anomaly_details = anomaly_details.sort_values("anomaly_score", ascending=False)
            anomaly_details.to_csv("anomaly_details.csv", index=False)
            mlflow.log_artifact("anomaly_details.csv")
            os.remove("anomaly_details.csv")

            print(f"\n  Top anomalies for {run_name}:")
            print(anomaly_details.head(5).to_string(index=False))

        # Save model with pickle and log as artifact
        model_filename = f"model-{run_name.replace(' ', '_')}.pkl"
        with open(model_filename, "wb") as f:
            pickle.dump(model, f)
        mlflow.log_artifact(model_filename)
        os.remove(model_filename)

        run_id = mlflow.active_run().info.run_id
        print(f"\n  {run_name}: {n_anomalies} anomalies ({anomaly_pct:.1f}%) "
              f"from {df_model.shape[0]} rows | mean score: {mean_score:.4f}")
        print(f"  Run ID: {run_id}")

    return model


# --- Main ---
trained_models = {}

print("=== Fleet-wide models ===")
fleet_df = build_dataset("fleet")
if not fleet_df.empty:
    trained_models["fleet-all-sensors"]    = train_and_log(fleet_df, "fleet-all-sensors",    [c for c in ALL_FEATURE_COLS  if c in fleet_df.columns])
    trained_models["fleet-sensors-only"]   = train_and_log(fleet_df, "fleet-sensors-only",   [c for c in SENSOR_COLS       if c in fleet_df.columns])
    trained_models["fleet-telemetry-only"] = train_and_log(fleet_df, "fleet-telemetry-only", [c for c in TELEMETRY_COLS    if c in fleet_df.columns])
    trained_models["fleet-c2-only"]        = train_and_log(fleet_df, "fleet-c2-only",        [c for c in C2_COLS           if c in fleet_df.columns])

print("\n=== Per-vehicle models ===")
all_files = glob.glob(f"{DATA_FOLDER}*.json")
prefixes  = set()
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

    trained_models[f"{prefix}-all"] = train_and_log(
        vehicle_df, f"{prefix}-all", [c for c in ALL_FEATURE_COLS if c in vehicle_df.columns])

    tel_cols = [c for c in TELEMETRY_COLS if c in vehicle_df.columns]
    if tel_cols:
        trained_models[f"{prefix}-telemetry"] = train_and_log(vehicle_df, f"{prefix}-telemetry", tel_cols)

    sen_cols = [c for c in SENSOR_COLS if c in vehicle_df.columns]
    if sen_cols:
        trained_models[f"{prefix}-sensors"] = train_and_log(vehicle_df, f"{prefix}-sensors", sen_cols)

    c2_cols = [c for c in C2_COLS if c in vehicle_df.columns]
    if c2_cols:
        trained_models[f"{prefix}-c2"] = train_and_log(vehicle_df, f"{prefix}-c2", c2_cols)

print(f"\nDone! Trained {len(trained_models)} models.")
print(f"View results at http://localhost:5050")

# trained_models dict is available for downstream use:
# model = trained_models["fleet-all-sensors"]
# score = model.score_one({"battery_pct": 12.0, "speed_knots": 24.1, ...})
# model.learn_one({"battery_pct": 12.0, "speed_knots": 24.1, ...})
