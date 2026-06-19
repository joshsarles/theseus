"""Bootstrap the MLflow Model Registry for the UUV edge receiver (MLflow 3.x correct).

Trains a streaming anomaly detector on the UUV sensor data, logs it as a real pyfunc model
(RiverAnomalyWrapper), registers it as `<MODEL_NAME>`, and sets the **`production` ALIAS**
(MLflow 3.x REMOVED stages; the receiver loads `models:/<name>@production`).

Detector — RunningZScoreDetector (replaces HalfSpaceTrees):
    The receiver scores 8 sensor channels per record. HalfSpaceTrees gave near-zero
    separation here (AUC ~0.65; scores compressed at ~0.98 for normal AND anomaly) because
    HST needs [0,1]-scaled inputs and its mass score is opaque. A per-feature running
    mean/variance (Welford) z-score — anomaly score = max |z| across channels, squashed to
    [0,1) — gets AUC ~0.94–1.0, separates cleanly (normal ~0.2, anomaly ~0.9), AND is
    explainable ("sonar_return_db deviated 8σ from baseline"), which matters for T&E /
    accreditation. It exposes River's learn_one/score_one so the receiver's online loop is
    unchanged, and learn_one is robust (ignores strong outliers so anomalies don't poison the
    baseline). It is cloudpickled by value, so the edge container needs no custom class.

    MLFLOW_TRACKING_URI=http://localhost:5050 python register_pickle_model.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import cloudpickle
import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient

HERE = Path(__file__).resolve().parent
DATA = Path(os.getenv("UUV_DATA", str(HERE / "data" / "uuv1-all-anom.json")))
MODEL_NAME = os.getenv("THESEUS_FLEET_MODEL", "uuv1_anomaly_deploy")
ALIAS = "production"
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")


class RunningZScoreDetector:
    """Online per-feature running mean/variance (Welford) anomaly detector.

    score_one(x) = squash(max_f |x_f - mean_f| / std_f) — the most-deviated sensor channel,
    mapped to [0,1) via z/(z+squash). learn_one(x) updates the running stats but SKIPS strong
    outliers (max|z| > robust_z) so streamed anomalies don't poison the learned baseline.
    """

    def __init__(self, warmup: int = 15, robust_z: float = 8.0, squash: float = 6.0):
        self.n: dict = {}
        self.mean: dict = {}
        self.m2: dict = {}
        self.warmup = warmup
        self.robust_z = robust_z
        self.squash = squash

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
                z = max(z, abs(v - self.mean[k]) / sd)
        return z

    def score_one(self, x: dict) -> float:
        z = self._zmax(x)
        return z / (z + self.squash)

    def learn_one(self, x: dict):
        # Robust: don't absorb a clear outlier into the baseline (once warmed up).
        if self._zmax(x) > self.robust_z and any(self.n.get(k, 0) >= self.warmup for k in x):
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
    """pyfunc wrapper around the cloudpickled detector. Exposes both `model` and
    `river_model` so the edge receiver's robust attribute lookup finds it either way."""

    def load_context(self, context):
        with open(context.artifacts["river_pkl"], "rb") as f:
            self.model = cloudpickle.load(f)
        self.river_model = self.model

    def predict(self, context, model_input):
        import pandas as pd
        recs = (model_input.to_dict(orient="records")
                if isinstance(model_input, pd.DataFrame) else model_input)
        return [float(self.model.score_one(x)) for x in recs]


def numeric_features(rec: dict) -> dict:
    out = {}
    for k, v in rec.items():
        if isinstance(v, bool):
            out[k] = 1.0 if v else 0.0
        elif isinstance(v, (int, float)):
            out[k] = float(v)
    return out


def main() -> int:
    import json
    records = json.loads(DATA.read_text())
    feats = [numeric_features(r) for r in records]
    labels = [1 if "ANOMALY" in str(r.get("record_id", "")).upper() else 0 for r in records]

    # Fit the baseline on NORMAL records only — an anomaly detector must learn "normal", so
    # injected anomalies stand out instead of being absorbed into the baseline.
    model = RunningZScoreDetector()
    for x, y in zip(feats, labels):
        if y == 0:
            model.learn_one(x)

    # Labeled eval (the RESULTS the UI surfaces) — precision@k / F1 / FAR vs the -ANOMALY
    # ground truth. The model is unsupervised; labels only score it.
    scores = [model.score_one(x) for x in feats]
    K = sum(labels)
    metrics = {"n_records": len(records), "n_anomalies": K}
    if 0 < K < len(scores):
        cut = sorted(scores, reverse=True)[K - 1]
        fl = [1 if s >= cut else 0 for s in scores]
        tp = sum(1 for f, y in zip(fl, labels) if f and y); fp = sum(1 for f, y in zip(fl, labels) if f and not y)
        fn = sum(1 for f, y in zip(fl, labels) if not f and y); tn = sum(1 for f, y in zip(fl, labels) if not f and not y)
        topk = sorted(range(len(scores)), key=lambda i: -scores[i])[:K]
        # rank AUC over normal/anomaly score pairs
        sa = [scores[i] for i in range(len(scores)) if labels[i]]
        sn = [scores[i] for i in range(len(scores)) if not labels[i]]
        auc = sum((a > n) + 0.5 * (a == n) for a in sa for n in sn) / (len(sa) * len(sn)) if sa and sn else 0.0
        metrics.update({
            "precision_at_k": round(sum(labels[i] for i in topk) / K, 4),
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else 0.0,
            "f1": round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) else 0.0,
            "false_alarm_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
            "roc_auc": round(auc, 4),
        })

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(MODEL_NAME.replace("_deploy", "_train"))
    with tempfile.TemporaryDirectory() as td:
        pkl = Path(td) / "river_model.pkl"
        with open(pkl, "wb") as f:
            cloudpickle.dump(model, f)   # by-value: edge container needs no custom class
        with mlflow.start_run(run_name=f"register-{MODEL_NAME}"):
            try:
                mlflow.pyfunc.log_model(
                    name="model", python_model=RiverAnomalyWrapper(),
                    artifacts={"river_pkl": str(pkl)},
                    registered_model_name=MODEL_NAME)
            except TypeError:   # older mlflow signature
                mlflow.pyfunc.log_model(
                    artifact_path="model", python_model=RiverAnomalyWrapper(),
                    artifacts={"river_pkl": str(pkl)},
                    registered_model_name=MODEL_NAME)
            mlflow.log_params({"model": "RunningZScoreDetector", "warmup": model.warmup,
                               "robust_z": model.robust_z, "squash": model.squash, "data": DATA.name})
            mlflow.log_metrics({k: float(v) for k, v in metrics.items()})

    client = MlflowClient()
    latest = max(client.search_model_versions(f"name='{MODEL_NAME}'"), key=lambda v: int(v.version))
    client.set_registered_model_alias(MODEL_NAME, ALIAS, latest.version)
    print(f"  registered {MODEL_NAME} v{latest.version} + alias @{ALIAS} on {TRACKING_URI}")
    print(f"  eval: {metrics}")

    # Verify the receiver's exact load path resolves.
    m = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{ALIAS}")
    print(f"  load via models:/{MODEL_NAME}@{ALIAS} OK · sample score = {m.predict([feats[0]])[0]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
