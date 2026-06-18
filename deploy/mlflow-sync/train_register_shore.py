#!/usr/bin/env python3
"""SHORE step — train the REAL CBM model and register it in the SHORE MLflow
Model Registry as `theseus-cbm`, logging a proper MLflow sklearn model flavor.

This is the "connected enclave" half of the shore->ship delivery. We REUSE the
demo's data contract and training recipe (import, do not rewrite) so the model is
the same CBM regressor demo/retrain.py trains on UCI #316:
    - same target resolution (demo.retrain._resolve_target)
    - same feature selection + 80/20 split (demo.retrain._load_xy)
    - same estimator: GradientBoostingRegressor(random_state=316)

Difference vs demo/retrain.py: we log an MLflow *model flavor* (mlflow.sklearn)
with a signature and register it, so:
    1. mlflow-export-import's `export-model` can export it across the gap, and
    2. the SHIP can `mlflow.pyfunc.load_model("models:/theseus-cbm/<v>")`.

We do NOT touch demo internals — we only import its pure helper functions.

Usage:
    MLFLOW_TRACKING_URI=http://127.0.0.1:5097 python train_register_shore.py
Prints a single JSON line on stdout with the registered name/version/run_id/rmse
so the orchestrator can capture it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEMO = REPO / "demo"
# import demo's pure helpers without executing its main()
sys.path.insert(0, str(DEMO))

import mlflow  # noqa: E402
import mlflow.sklearn  # noqa: E402
from mlflow.models.signature import infer_signature  # noqa: E402
from sklearn.ensemble import GradientBoostingRegressor  # noqa: E402

import retrain as demo_retrain  # demo/retrain.py — reuse, don't rewrite  # noqa: E402

MODEL_NAME = "theseus-cbm"


def main() -> int:
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        print("ERROR: MLFLOW_TRACKING_URI not set (must point at SHORE)", file=sys.stderr)
        return 2
    mlflow.set_tracking_uri(uri)

    # --- same data + recipe as the demo ------------------------------------
    target = demo_retrain._resolve_target(None)
    X, y, feats = demo_retrain._load_xy(target)
    cut = int(len(X) * 0.8)
    Xtr, ytr, Xte, yte = X[:cut], y[:cut], X[cut:], y[cut:]

    model = GradientBoostingRegressor(random_state=316)
    model.fit(Xtr, ytr)
    pred = list(model.predict(Xte))
    rmse = demo_retrain._rmse(pred, yte)

    # --- log a real MLflow model flavor + register it ----------------------
    mlflow.set_experiment(f"theseus-{target}")
    import pandas as pd
    Xte_df = pd.DataFrame(Xte, columns=feats)
    sig = infer_signature(Xte_df, model.predict(Xte_df))

    with mlflow.start_run(run_name="shore-register") as run:
        mlflow.log_params({
            "framework": "sklearn",
            "estimator": "GradientBoostingRegressor",
            "random_state": 316,
            "target": target,
            "n_features": len(feats),
            "n_train": len(Xtr),
            "n_test": len(Xte),
        })
        mlflow.log_metric("rmse", rmse)
        info = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            signature=sig,
            input_example=Xte_df.head(3),
            registered_model_name=MODEL_NAME,   # <- creates/extends the registry entry
        )
        run_id = run.info.run_id

    # resolve the version that registration just created
    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    ver = max(int(v.version) for v in versions)

    out = {
        "ok": True,
        "tracking_uri": uri,
        "model_name": MODEL_NAME,
        "version": ver,
        "run_id": run_id,
        "model_uri": info.model_uri,
        "rmse": round(rmse, 6),
        "target": target,
        "n_features": len(feats),
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
