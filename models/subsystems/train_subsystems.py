"""Train and register onboard anomaly models for each UUV subsystem.

Six models registered under models:/<name>@production:
  Labeled (UUV JSON):
    c2_deploy         serve/receiver/data/uuv1-c2-anom.json
    nav_deploy        serve/receiver/data/uuv1-telemetry-anom.json
    sonar_deploy      serve/receiver/data/uuv1-sensors-anom.json

  Unlabeled CSV (synthetic fault injection for eval):
    machinery_deploy  ingest/out/cbm.csv
    propulsion_deploy ingest/out/cmapss.csv
    auxiliary_deploy  ingest/out/metropt.csv

Detector: RunningZScoreDetector + RiverAnomalyWrapper + cloudpickle
  (identical recipe to serve/receiver/register_pickle_model.py; class copied
   verbatim so edge containers need no shared import).

Run:
  cd /Users/force/Developer/Theseus
  MLFLOW_TRACKING_URI=http://localhost:5050 \\
    deploy/mlflow/.venv312/bin/python models/subsystems/train_subsystems.py
"""
from __future__ import annotations

import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any

import cloudpickle
import mlflow
import mlflow.pyfunc
import pandas as pd
from mlflow.tracking import MlflowClient

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
DATA_JSON = REPO / "serve" / "receiver" / "data"
DATA_CSV = REPO / "ingest" / "out"
ALIAS = "production"
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Detector — copied verbatim from serve/receiver/register_pickle_model.py
# so each cloudpickle artifact is self-contained.
# ---------------------------------------------------------------------------

class RunningZScoreDetector:
    """Online per-feature running mean/variance (Welford) anomaly detector.

    score_one(x) = squash(max_f |x_f - mean_f| / std_f) — the most-deviated
    sensor channel, mapped to [0,1) via z/(z+squash).

    learn_one(x) updates running stats but SKIPS strong outliers
    (max|z| > robust_z) so streamed anomalies don't poison the baseline.

    min_abs_std: channels whose learned std falls below this absolute floor
      are skipped in _zmax. This prevents near-constant columns (e.g. a sensor
      that reads 288.0 K for the entire dataset) from dominating the anomaly
      score through numerical noise: dividing ~1e-13 float differences by the
      1e-6 fallback std yields spurious z~1e7. For most sensor streams the
      default of 1e-4 is safe; bump to 1e-2 for datasets with physical
      constants embedded as columns.
    """

    def __init__(
        self,
        warmup: int = 15,
        robust_z: float = 8.0,
        squash: float = 6.0,
        min_abs_std: float = 1e-4,
    ):
        self.n: dict = {}
        self.mean: dict = {}
        self.m2: dict = {}
        self.warmup = warmup
        self.robust_z = robust_z
        self.squash = squash
        self.min_abs_std = min_abs_std

    def _zmax(self, x: dict) -> float:
        z = 0.0
        for k, v in x.items():
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            n = self.n.get(k, 0)
            if n >= self.warmup:
                var = self.m2[k] / n
                sd = var ** 0.5 if var > 1e-12 else 1e-6
                if sd < self.min_abs_std:
                    continue  # skip near-constant channel; numerical noise, not signal
                z = max(z, abs(v - self.mean[k]) / sd)
        return z

    def score_one(self, x: dict) -> float:
        z = self._zmax(x)
        return z / (z + self.squash)

    def learn_one(self, x: dict) -> "RunningZScoreDetector":
        # Robust: don't absorb a clear outlier once warmed up.
        if self._zmax(x) > self.robust_z and any(
            self.n.get(k, 0) >= self.warmup for k in x
        ):
            return self
        for k, v in x.items():
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            self.n[k] = self.n.get(k, 0) + 1
            d = v - self.mean.get(k, 0.0)
            self.mean[k] = self.mean.get(k, 0.0) + d / self.n[k]
            self.m2[k] = self.m2.get(k, 0.0) + d * (v - self.mean[k])
        return self


class RiverAnomalyWrapper(mlflow.pyfunc.PythonModel):
    """pyfunc wrapper — exposes both `model` and `river_model` so the edge
    receiver's robust attribute lookup finds it either way."""

    def load_context(self, context: Any) -> None:
        with open(context.artifacts["river_pkl"], "rb") as f:
            self.model = cloudpickle.load(f)
        self.river_model = self.model

    def predict(self, context: Any, model_input: Any) -> list[float]:
        recs = (
            model_input.to_dict(orient="records")
            if isinstance(model_input, pd.DataFrame)
            else model_input
        )
        return [float(self.model.score_one(x)) for x in recs]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def numeric_features(rec: dict) -> dict:
    """Extract numeric (non-bool) fields as float."""
    out: dict = {}
    for k, v in rec.items():
        if isinstance(v, bool):
            out[k] = 1.0 if v else 0.0
        elif isinstance(v, (int, float)):
            out[k] = float(v)
    return out


def compute_metrics(scores: list[float], labels: list[int]) -> dict:
    """precision@k / F1 / FAR / ROC-AUC vs binary labels."""
    K = sum(labels)
    metrics: dict = {"n_records": len(scores), "n_anomalies": K}
    if 0 < K < len(scores):
        topk = sorted(range(len(scores)), key=lambda i: -scores[i])[:K]
        cut = scores[topk[-1]]
        fl = [1 if s >= cut else 0 for s in scores]
        tp = sum(1 for f, y in zip(fl, labels) if f and y)
        fp = sum(1 for f, y in zip(fl, labels) if f and not y)
        fn = sum(1 for f, y in zip(fl, labels) if not f and y)
        tn = sum(1 for f, y in zip(fl, labels) if not f and not y)
        sa = [scores[i] for i in range(len(scores)) if labels[i]]
        sn = [scores[i] for i in range(len(scores)) if not labels[i]]
        auc = (
            sum((a > n) + 0.5 * (a == n) for a in sa for n in sn)
            / (len(sa) * len(sn))
            if sa and sn
            else 0.0
        )
        metrics.update(
            {
                "precision_at_k": round(sum(labels[i] for i in topk) / K, 4),
                "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
                "recall": round(tp / (tp + fn), 4) if (tp + fn) else 0.0,
                "f1": round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) else 0.0,
                "false_alarm_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
                "roc_auc": round(auc, 4),
            }
        )
    return metrics


def register_model(
    model: RunningZScoreDetector,
    model_name: str,
    metrics: dict,
    extra_params: dict | None = None,
) -> str:
    """Log model to MLflow, register it, set @production alias. Returns version str."""
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(model_name.replace("_deploy", "_train"))
    client = MlflowClient()

    with tempfile.TemporaryDirectory() as td:
        pkl = Path(td) / "river_model.pkl"
        with open(pkl, "wb") as f:
            cloudpickle.dump(model, f)

        with mlflow.start_run(run_name=f"register-{model_name}"):
            params = {
                "model": "RunningZScoreDetector",
                "warmup": model.warmup,
                "robust_z": model.robust_z,
                "squash": model.squash,
                "min_abs_std": model.min_abs_std,
                "random_seed": RANDOM_SEED,
            }
            if extra_params:
                params.update(extra_params)
            mlflow.log_params(params)
            mlflow.log_metrics({k: float(v) for k, v in metrics.items()})

            try:
                mlflow.pyfunc.log_model(
                    name="model",
                    python_model=RiverAnomalyWrapper(),
                    artifacts={"river_pkl": str(pkl)},
                    registered_model_name=model_name,
                )
            except TypeError:  # older mlflow signature fallback
                mlflow.pyfunc.log_model(
                    artifact_path="model",
                    python_model=RiverAnomalyWrapper(),
                    artifacts={"river_pkl": str(pkl)},
                    registered_model_name=model_name,
                )

    latest = max(
        client.search_model_versions(f"name='{model_name}'"),
        key=lambda v: int(v.version),
    )
    client.set_registered_model_alias(model_name, ALIAS, latest.version)
    return latest.version


# ---------------------------------------------------------------------------
# Task A: Labeled UUV JSON subsystems
# ---------------------------------------------------------------------------

def train_labeled_json(
    json_path: Path,
    model_name: str,
) -> tuple[RunningZScoreDetector, dict, list[dict]]:
    """Train RunningZScoreDetector on NORMAL rows; eval vs ANOMALY labels."""
    records = json.loads(json_path.read_text())
    feats = [numeric_features(r) for r in records]
    labels = [
        1 if "ANOMALY" in str(r.get("record_id", "")).upper() else 0
        for r in records
    ]

    model = RunningZScoreDetector()
    for x, y in zip(feats, labels):
        if y == 0:
            model.learn_one(x)

    scores = [model.score_one(x) for x in feats]
    metrics = compute_metrics(scores, labels)
    metrics["eval_type"] = 0.0  # 0 = labeled ground truth

    print(
        f"  [{model_name}] n={len(records)}, anomalies={sum(labels)}, "
        f"AUC={metrics.get('roc_auc', 'N/A')}, F1={metrics.get('f1', 'N/A')}, "
        f"FAR={metrics.get('false_alarm_rate', 'N/A')}"
    )
    return model, metrics, feats


# ---------------------------------------------------------------------------
# Task B: Unlabeled CSVs — train on numeric cols, inject synthetic faults
# ---------------------------------------------------------------------------

def inject_synthetic_faults(
    df: pd.DataFrame,
    numeric_cols: list[str],
    n_faults: int = 30,
    spike_multiplier: float = 12.0,
    seed: int = RANDOM_SEED,
    min_std_pct: float = 0.05,
) -> tuple[list[dict], list[int]]:
    """Inject synthetic spikes into a random sample of rows (held-out test set).

    Strategy: pick n_faults rows from the LAST 20% of data (tail = highest
    operational stress). For each, spike 2-3 VARIABLE channels by
    spike_multiplier * std above the mean. Near-constant channels (std < min_std_pct
    of max-std across all cols) are excluded from spiking — they would generate
    astronomically large z-scores even for tiny absolute changes because the
    RunningZScoreDetector divides by their near-zero std, which also means the
    baseline already fires on those channels for normal rows in the tail and
    the fault rows are indistinguishable. Excluding them keeps the synthetic
    faults clearly localized to channels that have real operational variance.

    This gives an honest AUC estimate:
      - spiked rows are clearly out-of-distribution relative to the trained baseline
      - non-spiked tail rows remain label=0 (true negatives)
    Returns (records_as_dicts, labels) for the held-out test split only.
    Label origin is always reported as 'synthetic' in MLflow params.
    """
    rng = random.Random(seed)
    n = len(df)
    tail_start = int(n * 0.80)

    # Compute per-column mean + std on training portion (first 80%)
    train_df = df.iloc[:tail_start]
    col_mean = {c: float(train_df[c].mean()) for c in numeric_cols}
    col_std = {c: max(float(train_df[c].std()), 1e-9) for c in numeric_cols}

    # Identify spikeable columns: std >= min_std_pct of the maximum std seen
    max_std = max(col_std.values())
    std_threshold = min_std_pct * max_std
    spikeable = [c for c in numeric_cols if col_std[c] >= std_threshold]
    if len(spikeable) < 2:
        # Fallback: take top-3 by std
        spikeable = sorted(numeric_cols, key=lambda c: -col_std[c])[:3]

    # Build test records (tail rows, unmodified)
    test_df = df.iloc[tail_start:].copy()
    labels = [0] * len(test_df)
    fault_row_positions = rng.sample(range(len(test_df)), min(n_faults, len(test_df)))

    for pos in fault_row_positions:
        spike_cols = rng.sample(spikeable, min(3, len(spikeable)))
        for col in spike_cols:
            direction = rng.choice([1, -1])
            test_df.iloc[pos, test_df.columns.get_loc(col)] = (
                col_mean[col] + direction * spike_multiplier * col_std[col]
            )
        labels[pos] = 1  # synthetic fault

    records = test_df[numeric_cols].to_dict(orient="records")
    return records, labels


def train_unlabeled_csv(
    csv_path: Path,
    model_name: str,
    exclude_cols: list[str] | None = None,
    n_faults: int = 30,
    spike_multiplier: float = 12.0,
    min_abs_std: float = 1e-4,
) -> tuple[RunningZScoreDetector, dict, list[dict]]:
    """Train on first 80% (normal baseline); eval with synthetic fault injection."""
    df = pd.read_csv(csv_path)
    exclude = set(exclude_cols or [])
    numeric_cols = [
        c for c in df.select_dtypes(include="number").columns if c not in exclude
    ]

    n = len(df)
    tail_start = int(n * 0.80)
    train_df = df.iloc[:tail_start]

    model = RunningZScoreDetector(min_abs_std=min_abs_std)
    for rec in train_df[numeric_cols].to_dict(orient="records"):
        model.learn_one(rec)

    # Synthetic fault eval on tail (min_std_pct=0.05 excludes near-constant channels)
    test_records, labels = inject_synthetic_faults(
        df, numeric_cols, n_faults=n_faults, spike_multiplier=spike_multiplier,
        min_std_pct=0.05,
    )
    scores = [model.score_one(x) for x in test_records]
    metrics = compute_metrics(scores, labels)
    metrics["eval_type"] = 1.0  # 1 = synthetic fault injection
    metrics["n_train"] = float(tail_start)
    metrics["n_synthetic_faults"] = float(sum(labels))
    metrics["spike_multiplier"] = float(spike_multiplier)

    print(
        f"  [{model_name}] trained={tail_start} rows, "
        f"synthetic faults={sum(labels)}, AUC={metrics.get('roc_auc', 'N/A')}, "
        f"F1={metrics.get('f1', 'N/A')}, FAR={metrics.get('false_alarm_rate', 'N/A')}"
    )
    return model, metrics, [numeric_features(r) for r in train_df[numeric_cols].head(5).to_dict(orient="records")]


# ---------------------------------------------------------------------------
# Main — train all six subsystems and register
# ---------------------------------------------------------------------------

LABELED_JOBS = [
    ("uuv1-c2-anom.json", "c2_deploy"),
    ("uuv1-telemetry-anom.json", "nav_deploy"),
    ("uuv1-sensors-anom.json", "sonar_deploy"),
]

UNLABELED_JOBS = [
    # (filename, model_name, exclude_cols, min_abs_std)
    # cbm: compressor_inlet_temp + compressor_inlet_press are physical constants
    # (std=0 across entire dataset). min_abs_std=1e-2 skips them so numerical
    # noise doesn't saturate the detector; true sensor faults still spike high.
    ("cbm.csv", "machinery_deploy", [], 1e-2),
    # cmapss 'rul' is a regression target, not a feature — exclude it
    ("cmapss.csv", "propulsion_deploy", ["rul"], 1e-4),
    # metropt 'is_anomaly' is the label — exclude from features
    ("metropt.csv", "auxiliary_deploy", ["is_anomaly"], 1e-4),
]


def main() -> int:
    mlflow.set_tracking_uri(TRACKING_URI)
    client = MlflowClient()

    registry_table: list[dict] = []
    sample_feats: dict[str, list[dict]] = {}

    print("=== Labeled UUV JSON subsystems ===")
    for fname, model_name in LABELED_JOBS:
        json_path = DATA_JSON / fname
        model, metrics, feats = train_labeled_json(json_path, model_name)
        version = register_model(
            model, model_name, metrics,
            extra_params={"data": fname, "eval_type": "labeled_ground_truth"},
        )
        registry_table.append({
            "model": model_name,
            "version": version,
            "eval_type": "labeled",
            "roc_auc": metrics.get("roc_auc", "-"),
            "f1": metrics.get("f1", "-"),
            "far": metrics.get("false_alarm_rate", "-"),
            "precision_at_k": metrics.get("precision_at_k", "-"),
        })
        sample_feats[model_name] = feats[:1]
        print(f"  -> registered {model_name} v{version} @{ALIAS}")

    print()
    print("=== Unlabeled CSV subsystems (synthetic fault eval) ===")
    for fname, model_name, exclude_cols, min_abs_std in UNLABELED_JOBS:
        csv_path = DATA_CSV / fname
        model, metrics, feats = train_unlabeled_csv(
            csv_path, model_name, exclude_cols=exclude_cols, min_abs_std=min_abs_std,
        )
        version = register_model(
            model, model_name, metrics,
            extra_params={
                "data": fname,
                "eval_type": "synthetic_fault_injection",
                "exclude_cols": ",".join(exclude_cols) if exclude_cols else "none",
            },
        )
        registry_table.append({
            "model": model_name,
            "version": version,
            "eval_type": "synthetic",
            "roc_auc": metrics.get("roc_auc", "-"),
            "f1": metrics.get("f1", "-"),
            "far": metrics.get("false_alarm_rate", "-"),
            "precision_at_k": metrics.get("precision_at_k", "-"),
        })
        sample_feats[model_name] = feats[:1]
        print(f"  -> registered {model_name} v{version} @{ALIAS}")

    # -----------------------------------------------------------------------
    # Verification: load @production alias and score a sample for each model
    # -----------------------------------------------------------------------
    print()
    print("=== Registry verification ===")
    for entry in registry_table:
        name = entry["model"]
        uri = f"models:/{name}@{ALIAS}"
        loaded = mlflow.pyfunc.load_model(uri)
        sample = sample_feats[name]
        score = loaded.predict(sample)[0]
        entry["sample_score"] = round(float(score), 4)
        print(f"  {name} v{entry['version']} @{ALIAS} -> sample score = {score:.4f}  OK")

    # -----------------------------------------------------------------------
    # Registry table printout
    # -----------------------------------------------------------------------
    print()
    print("=" * 90)
    print(f"{'MODEL':<25} {'VER':>4}  {'EVAL':<10}  {'AUC':>7}  {'F1':>7}  {'FAR':>7}  {'P@K':>7}  {'SAMPLE':>8}")
    print("-" * 90)
    for r in registry_table:
        print(
            f"  {r['model']:<23} {r['version']:>4}  {r['eval_type']:<10}  "
            f"{str(r['roc_auc']):>7}  {str(r['f1']):>7}  {str(r['far']):>7}  "
            f"{str(r['precision_at_k']):>7}  {str(r['sample_score']):>8}"
        )
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
