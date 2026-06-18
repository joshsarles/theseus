"""
Train a UUV1 River anomaly model and log artifacts to MLflow.

Purpose:
- Uses ONLY the full UUV1 files by default:
    data/UUV1-sensors.json
    data/UUV1-telemetry.json
    data/UUV1-c2.json
- Ignores split files such as UUV1-sensors-baseline.json and UUV1-sensors-stream.json.
- Builds one row per time-step by aligning the three files by row order.
- Trains a River HalfSpaceTrees anomaly detector online.
- Writes local statistical/model artifacts to outputs/ and logs them to MLflow.

Expected folder:
    project/
      train.py
      data/
        UUV1-sensors.json
        UUV1-telemetry.json
        UUV1-c2.json

Environment variables, optional:
    DATA_FOLDER=./data
    OUTPUT_DIR=./outputs
    MLFLOW_TRACKING_URI=http://localhost:5050
    MLFLOW_EXPERIMENT_NAME=UUV1 Anomaly Detection - HST
    VEHICLE_PREFIX=UUV1
    ANOMALY_THRESHOLD=0.7
    TRAIN_SUBMODELS=false
"""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Iterable

import mlflow
import numpy as np
import pandas as pd
from river import anomaly, preprocessing


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DATA_FOLDER = Path(os.getenv("DATA_FOLDER", "data"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
VEHICLE_PREFIX = os.getenv("VEHICLE_PREFIX", "UUV1")

N_TREES = int(os.getenv("N_TREES", "25"))
HEIGHT = int(os.getenv("HEIGHT", "15"))
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "250"))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.7"))
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "42"))
TRAIN_SUBMODELS = os.getenv("TRAIN_SUBMODELS", "false").lower() in {"1", "true", "yes"}

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "UUV1 Anomaly Detection - HST")

# UUV sensor schema: actual fields in UUV1-sensors.json.
SENSOR_COLS = [
    "water_temp_c",
    "salinity_ppt",
    "turbidity_ntu",
    "sonar_range_m",
    "sonar_bearing_deg",
    "sonar_return_db",
    "pressure_bar",
]

TELEMETRY_COLS = [
    "latitude_deg",
    "longitude_deg",
    "speed_knots",
    "heading_deg",
    "depth_m",
    "altitude_asl_m",
    "roll_deg",
    "pitch_deg",
    "battery_pct",
    "signal_strength_dbm",
    "hdop",
]

C2_COLS = [
    "sequence_num",
    "payload_bytes",
    "latency_ms",
]

CONTEXT_COLS = [
    "record_id",
    "vehicle_id",
    "vehicle_name",
    "vehicle_type",
    "vehicle_class",
    "mission_state",
    "timestamp_utc",
]

ALL_FEATURE_COLS = C2_COLS + SENSOR_COLS + TELEMETRY_COLS


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def read_json_records(path: Path) -> pd.DataFrame:
    """Read a JSON list, or a dict containing a list under common keys, into a DataFrame."""
    if not path.exists():
        print(f"  Missing optional file: {path}")
        return pd.DataFrame()

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return pd.DataFrame(data)

    if isinstance(data, dict):
        for key in ("data", "records", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return pd.DataFrame(value)
        return pd.DataFrame([data])

    raise ValueError(f"Unsupported JSON structure in {path}")


def keep_columns(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """Return only the requested columns that exist in df."""
    existing = [c for c in cols if c in df.columns]
    return df[existing].copy() if existing else pd.DataFrame(index=df.index)


def prefix_context_columns(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Avoid context-column collisions when aligning sensor/telemetry/C2 by row order."""
    rename_map = {c: f"{source}_{c}" for c in CONTEXT_COLS if c in df.columns}
    return df.rename(columns=rename_map)


def build_uuv1_dataset() -> pd.DataFrame:
    """
    Build a single UUV1 training table from exact full files only.

    Important: this intentionally does not glob UUV1*.json, because that would pull
    in UUV1-sensors-baseline.json and UUV1-sensors-stream.json. It also does not
    join on record_id, because the three files have different record IDs for the
    same time-step. We align by row order, which matches the synthetic data layout.
    """
    sensors_path = DATA_FOLDER / f"{VEHICLE_PREFIX}-sensors.json"
    telemetry_path = DATA_FOLDER / f"{VEHICLE_PREFIX}-telemetry.json"
    c2_path = DATA_FOLDER / f"{VEHICLE_PREFIX}-c2.json"

    sensors_raw = read_json_records(sensors_path)
    telemetry_raw = read_json_records(telemetry_path)
    c2_raw = read_json_records(c2_path)

    print("Input row counts:")
    print(f"  sensors:   {len(sensors_raw)} from {sensors_path}")
    print(f"  telemetry: {len(telemetry_raw)} from {telemetry_path}")
    print(f"  c2:        {len(c2_raw)} from {c2_path}")

    frames: list[pd.DataFrame] = []

    if not sensors_raw.empty:
        sensors = pd.concat(
            [prefix_context_columns(keep_columns(sensors_raw, CONTEXT_COLS), "sensor"),
             keep_columns(sensors_raw, SENSOR_COLS)],
            axis=1,
        )
        frames.append(sensors.reset_index(drop=True))

    if not telemetry_raw.empty:
        telemetry = pd.concat(
            [prefix_context_columns(keep_columns(telemetry_raw, CONTEXT_COLS), "telemetry"),
             keep_columns(telemetry_raw, TELEMETRY_COLS)],
            axis=1,
        )
        frames.append(telemetry.reset_index(drop=True))

    if not c2_raw.empty:
        c2 = pd.concat(
            [prefix_context_columns(keep_columns(c2_raw, CONTEXT_COLS), "c2"),
             keep_columns(c2_raw, C2_COLS)],
            axis=1,
        )
        frames.append(c2.reset_index(drop=True))

    if not frames:
        raise RuntimeError(f"No UUV1 data found in {DATA_FOLDER.resolve()}")

    df = pd.concat(frames, axis=1)

    # Add unified display context columns, preferring telemetry, then sensor, then c2.
    for col in CONTEXT_COLS:
        candidates = [f"telemetry_{col}", f"sensor_{col}", f"c2_{col}"]
        present = [c for c in candidates if c in df.columns]
        if present:
            df[col] = df[present].bfill(axis=1).iloc[:, 0]

    # Drop duplicate column names if any slipped through.
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def prepare_model_frame(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Select numeric features, coerce values, and fill missing numeric cells."""
    feature_cols = [c for c in feature_cols if c in df.columns]
    if not feature_cols:
        raise RuntimeError("None of the requested feature columns exist in the dataset.")

    df_model = df[feature_cols].copy()

    # Coerce numerics. Non-numeric fields are not model features for this River HST model.
    for col in df_model.columns:
        df_model[col] = pd.to_numeric(df_model[col], errors="coerce")

    df_model = df_model.select_dtypes(include=[np.number])

    if df_model.empty:
        raise RuntimeError("No numeric features remain after preprocessing.")

    medians = df_model.median(numeric_only=True)
    df_model = df_model.fillna(medians).fillna(0.0)
    return df_model, list(df_model.columns)


def explain_anomalies(
    scores_series: pd.Series,
    df_model: pd.DataFrame,
    df_context: pd.DataFrame,
    top_n: int = 3,
) -> pd.DataFrame:
    """For each anomaly row, show the features with the largest absolute z-scores."""
    results = []
    numeric = df_model.select_dtypes(include=[np.number])
    means = numeric.mean()
    stds = numeric.std().replace(0, 1).fillna(1)
    z_scores = (numeric - means) / stds

    for idx in numeric.index:
        score = float(scores_series.loc[idx])
        if score < ANOMALY_THRESHOLD:
            continue

        row_z = z_scores.loc[idx].abs()
        top_features = row_z.nlargest(top_n)

        result = {
            "row_index": int(idx),
            "record_id": df_context.loc[idx, "record_id"] if "record_id" in df_context.columns else idx,
            "vehicle_id": df_context.loc[idx, "vehicle_id"] if "vehicle_id" in df_context.columns else "",
            "vehicle_type": df_context.loc[idx, "vehicle_type"] if "vehicle_type" in df_context.columns else "",
            "timestamp_utc": df_context.loc[idx, "timestamp_utc"] if "timestamp_utc" in df_context.columns else "",
            "anomaly_score": round(score, 6),
        }

        for feat, z in top_features.items():
            result[f"flag_{feat}"] = round(float(numeric.loc[idx, feat]), 4)
            result[f"flag_{feat}_zscore"] = round(float(z), 2)
            result[f"flag_{feat}_mean"] = round(float(means[feat]), 4)

        results.append(result)

    return pd.DataFrame(results)


def write_statistical_output(
    df_model: pd.DataFrame,
    scores_series: pd.Series,
    run_name: str,
    output_dir: Path,
) -> Path:
    """Write a compact statistical summary CSV for the trained feature set."""
    stats = df_model.describe().T.reset_index().rename(columns={"index": "feature"})
    stats["missing_count_after_fill"] = 0
    stats["mean_abs_zscore"] = ((df_model - df_model.mean()) / df_model.std().replace(0, 1)).abs().mean().values

    summary_rows = pd.DataFrame(
        [
            {"feature": "__rows__", "count": len(df_model)},
            {"feature": "__features__", "count": df_model.shape[1]},
            {"feature": "__mean_anomaly_score__", "count": float(scores_series.mean())},
            {"feature": "__max_anomaly_score__", "count": float(scores_series.max())},
            {"feature": "__anomaly_threshold__", "count": ANOMALY_THRESHOLD},
            {"feature": "__n_anomalies__", "count": int((scores_series >= ANOMALY_THRESHOLD).sum())},
        ]
    )

    out = pd.concat([summary_rows, stats], ignore_index=True, sort=False)
    path = output_dir / f"statistical_output-{run_name}.csv"
    out.to_csv(path, index=False)
    return path


def train_and_log(df: pd.DataFrame, run_name: str, feature_cols: list[str]):
    """Train a River HalfSpaceTrees model online and log outputs locally + to MLflow."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df_model, used_features = prepare_model_frame(df, feature_cols)

    if df_model.shape[0] < 10:
        raise RuntimeError(f"Not enough rows to train {run_name}: {df_model.shape[0]}")

    model = preprocessing.StandardScaler() | anomaly.HalfSpaceTrees(
        n_trees=N_TREES,
        height=HEIGHT,
        window_size=WINDOW_SIZE,
        seed=RANDOM_STATE,
    )

    scores = []
    for _, row in df_model.iterrows():
        x = row.to_dict()
        score = model.score_one(x)   # score before learning
        model.learn_one(x)           # online update
        scores.append(float(score))

    scores_series = pd.Series(scores, index=df_model.index)
    n_anomalies = int((scores_series >= ANOMALY_THRESHOLD).sum())
    anomaly_pct = n_anomalies / len(scores_series) * 100
    mean_score = float(scores_series.mean())

    context_cols_present = [c for c in CONTEXT_COLS if c in df.columns]
    df_context = df[context_cols_present].copy().reset_index(drop=True)

    results = df_context.copy()
    results["row_index"] = df_model.index
    results["anomaly_score"] = scores_series.values
    results["is_anomaly"] = scores_series.values >= ANOMALY_THRESHOLD
    results = results.sort_values("anomaly_score", ascending=False)

    anomalies_path = OUTPUT_DIR / f"anomalies_found-{run_name}.csv"
    results.to_csv(anomalies_path, index=False)

    details = explain_anomalies(
        scores_series.reset_index(drop=True),
        df_model.reset_index(drop=True),
        df_context,
    )
    details_path = OUTPUT_DIR / f"anomaly_details-{run_name}.csv"
    #details.sort_values("anomaly_score", ascending=False).to_csv(details_path, index=False)
    if not details.empty and "anomaly_score" in details.columns:
        details = details.sort_values("anomaly_score", ascending=False)

    details.to_csv(details_path, index=False)
    stats_path = write_statistical_output(df_model, scores_series, run_name, OUTPUT_DIR)

    model_path = OUTPUT_DIR / f"model-{run_name}.pkl"
    with model_path.open("wb") as f:
        pickle.dump(model, f)

    feature_schema_path = OUTPUT_DIR / f"feature_schema-{run_name}.json"
    feature_schema_path.write_text(json.dumps({"features": used_features}, indent=2), encoding="utf-8")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name=run_name) as run:
        try:
            dataset = mlflow.data.from_pandas(df_model, name=run_name)
            mlflow.log_input(dataset, context="training")
        except Exception as exc:
            print(f"  Warning: could not log MLflow dataset input: {exc}")

        mlflow.log_param("vehicle_prefix", VEHICLE_PREFIX)
        mlflow.log_param("model_type", "River HalfSpaceTrees")
        mlflow.log_param("n_trees", N_TREES)
        mlflow.log_param("height", HEIGHT)
        mlflow.log_param("window_size", WINDOW_SIZE)
        mlflow.log_param("threshold", ANOMALY_THRESHOLD)
        mlflow.log_param("random_state", RANDOM_STATE)
        mlflow.log_param("n_rows", df_model.shape[0])
        mlflow.log_param("n_features", df_model.shape[1])
        mlflow.log_param("features", used_features)
        mlflow.log_param("source_files", [
            str(DATA_FOLDER / f"{VEHICLE_PREFIX}-sensors.json"),
            str(DATA_FOLDER / f"{VEHICLE_PREFIX}-telemetry.json"),
            str(DATA_FOLDER / f"{VEHICLE_PREFIX}-c2.json"),
        ])

        mlflow.log_metric("n_anomalies", n_anomalies)
        mlflow.log_metric("anomaly_pct", round(anomaly_pct, 2))
        mlflow.log_metric("mean_anomaly_score", round(mean_score, 6))
        mlflow.log_metric("max_anomaly_score", round(float(scores_series.max()), 6))

        for artifact in [anomalies_path, details_path, stats_path, model_path, feature_schema_path]:
            mlflow.log_artifact(str(artifact))

        print(f"\n{run_name}")
        print(f"  rows: {df_model.shape[0]}")
        print(f"  features: {df_model.shape[1]} -> {used_features}")
        print(f"  anomalies: {n_anomalies} ({anomaly_pct:.2f}%)")
        print(f"  mean score: {mean_score:.6f}")
        print(f"  MLflow run ID: {run.info.run_id}")
        print(f"  local outputs: {OUTPUT_DIR.resolve()}")

    return model


def main() -> None:
    print("=== UUV1-only River anomaly training ===")
    print(f"Data folder: {DATA_FOLDER.resolve()}")
    print(f"Output dir:  {OUTPUT_DIR.resolve()}")
    print(f"MLflow URI:  {MLFLOW_TRACKING_URI}")

    df = build_uuv1_dataset()
    print(f"Merged UUV1 training table: {df.shape[0]} rows x {df.shape[1]} columns")

    # Main demo model: one integrated UUV1 model.
    train_and_log(df, f"{VEHICLE_PREFIX}-all", [c for c in ALL_FEATURE_COLS if c in df.columns])

    # Optional compatibility mode if you still want per-source models.
    if TRAIN_SUBMODELS:
        sensor_cols = [c for c in SENSOR_COLS if c in df.columns]
        telemetry_cols = [c for c in TELEMETRY_COLS if c in df.columns]
        c2_cols = [c for c in C2_COLS if c in df.columns]

        if sensor_cols:
            train_and_log(df, f"{VEHICLE_PREFIX}-sensors", sensor_cols)
        if telemetry_cols:
            train_and_log(df, f"{VEHICLE_PREFIX}-telemetry", telemetry_cols)
        if c2_cols:
            train_and_log(df, f"{VEHICLE_PREFIX}-c2", c2_cols)

    print("\nDone.")


if __name__ == "__main__":
    main()
