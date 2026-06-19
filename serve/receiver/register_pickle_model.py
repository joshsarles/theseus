"""Bootstrap the MLflow Model Registry for the UUV edge receiver (MLflow 3.x correct).

Trains a River HalfSpaceTrees anomaly detector on the UUV data, logs it as a real pyfunc
model (RiverAnomalyWrapper — picklable River model), registers it as `uuv1_anomaly_deploy`,
and sets the **`production` ALIAS**. MLflow 3.x REMOVED model stages, so the old
`transition_model_version_stage(stage="Production")` no longer resolves — the receiver loads
`models:/uuv1_anomaly_deploy@production`. This is the bootstrap that makes that load succeed.

    MLFLOW_TRACKING_URI=http://localhost:5050 python register_pickle_model.py
"""
from __future__ import annotations

import json
import os
import pickle
import tempfile
from pathlib import Path

import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
from river import anomaly, preprocessing

HERE = Path(__file__).resolve().parent
DATA = Path(os.getenv("UUV_DATA", str(HERE / "data" / "uuv1-all-anom.json")))
MODEL_NAME = os.getenv("THESEUS_FLEET_MODEL", "uuv1_anomaly_deploy")
ALIAS = "production"
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")


class RiverAnomalyWrapper(mlflow.pyfunc.PythonModel):
    """pyfunc wrapper around a pickled River anomaly model. Exposes both `model` and
    `river_model` so the edge receiver's robust attribute lookup finds it either way."""

    def load_context(self, context):
        with open(context.artifacts["river_pkl"], "rb") as f:
            self.model = pickle.load(f)
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
    records = json.loads(DATA.read_text())
    feats = [numeric_features(r) for r in records]
    # River HST + scaler; warm-up pass so the window fills and "normal" is established.
    model = preprocessing.StandardScaler() | anomaly.HalfSpaceTrees(
        n_trees=25, height=12, window_size=50, seed=42)
    for x in feats:
        model.learn_one(x)

    # Labeled eval (the RESULTS the UI surfaces) — precision@k / F1 / FAR vs the -ANOMALY
    # ground truth tagged in record_id. The model is unsupervised; labels only score it.
    labels = [1 if "ANOMALY" in str(r.get("record_id", "")).upper() else 0 for r in records]
    scores = [model.score_one(x) for x in feats]
    K = sum(labels)
    metrics = {"n_records": len(records), "n_anomalies": K}
    if 0 < K < len(scores):
        cut = sorted(scores, reverse=True)[K - 1]
        fl = [1 if s >= cut else 0 for s in scores]
        tp = sum(1 for f, y in zip(fl, labels) if f and y); fp = sum(1 for f, y in zip(fl, labels) if f and not y)
        fn = sum(1 for f, y in zip(fl, labels) if not f and y); tn = sum(1 for f, y in zip(fl, labels) if not f and not y)
        topk = sorted(range(len(scores)), key=lambda i: -scores[i])[:K]
        metrics.update({
            "precision_at_k": round(sum(labels[i] for i in topk) / K, 4),
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else 0.0,
            "f1": round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) else 0.0,
            "false_alarm_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
        })

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(MODEL_NAME.replace("_deploy", "_train"))
    with tempfile.TemporaryDirectory() as td:
        pkl = Path(td) / "river_model.pkl"
        with open(pkl, "wb") as f:
            pickle.dump(model, f)
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
            mlflow.log_params({"model": "HalfSpaceTrees", "n_trees": 25, "height": 12,
                               "window_size": 50, "data": DATA.name})
            mlflow.log_metrics({k: float(v) for k, v in metrics.items()})

    client = MlflowClient()
    latest = max(client.search_model_versions(f"name='{MODEL_NAME}'"), key=lambda v: int(v.version))
    client.set_registered_model_alias(MODEL_NAME, ALIAS, latest.version)
    print(f"  registered {MODEL_NAME} v{latest.version} + alias @{ALIAS} on {TRACKING_URI}")

    # Verify the receiver's exact load path resolves.
    m = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{ALIAS}")
    print(f"  load via models:/{MODEL_NAME}@{ALIAS} OK · sample score = {m.predict([feats[0]])[0]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
