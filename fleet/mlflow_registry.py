"""Node 3 fleet model registry — MLflow-optional, model-agnostic glue.

The locked architecture (docs/vision/UUV_FLEET_ARCHITECTURE.md): **Node 3 coordinates the
fleet's models via MLflow.** This module is the glue. The fleet brain REGISTERS each
accepted merged model (+ metrics) into the MLflow registry, and can LOAD the latest
registered model as the incumbent.

Two design rules so it never blocks the team and never reworks:
  • MLflow-OPTIONAL — if MLFLOW_TRACKING_URI isn't set OR mlflow won't import (the py3.14
    host breaks mlflow's import), EVERY call is a safe no-op and the local fleet_model.json
    stays the source of truth. The flywheel runs identically with or without the Node-3
    server. When Tommy/Juan's MLflow server is up and MLFLOW_TRACKING_URI points at it, the
    same calls light up the registry — no code change.
  • MODEL-AGNOSTIC — it logs whatever model-artifact FILE you hand it (.onnx, .skops, .json,
    .pt). Claire's sequence-autoencoder registers exactly the way the demo Ridge model does.

Team contract: register the UUV own-systems model under MODEL_NAME = 'theseus-uuv'.
"""
from __future__ import annotations

import os
from pathlib import Path

# The fleet registry's canonical model name (the contract Claire/THESEUS register under).
MODEL_NAME = os.environ.get("THESEUS_FLEET_MODEL", "theseus-uuv")
EXPERIMENT = os.environ.get("THESEUS_FLEET_EXPERIMENT", "theseus-fleet")


def _mlflow():
    """Return the mlflow module iff usable (URI set + importable), else None (-> no-op).

    Gated on MLFLOW_TRACKING_URI so a bare run never tries to reach a server; wrapped in
    try/except so the py3.14 host (where mlflow's import is broken) silently falls back."""
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        return None
    try:
        import mlflow  # noqa: F401
        return mlflow
    except Exception:
        return None


def available() -> bool:
    """True iff the MLflow registry is reachable (else the caller uses local files)."""
    return _mlflow() is not None


def log_fleet_round(metrics: dict, model_path: Path | str | None = None,
                    *, model_name: str = MODEL_NAME, run_name: str | None = None) -> bool:
    """Log one fleet-merge round to MLflow: numeric metrics + the model artifact, then
    register the artifact as a version of `model_name` (the fleet registry).

    Returns True if logged, False if MLflow is unavailable (no-op — local files stand).
    Model-agnostic: `model_path` is any artifact file."""
    mlflow = _mlflow()
    if mlflow is None:
        return False
    try:
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name=run_name):
            mlflow.log_metrics({k: float(v) for k, v in (metrics or {}).items()
                                if isinstance(v, (int, float))})
            if model_path and Path(model_path).exists():
                mlflow.log_artifact(str(model_path), artifact_path="model")
                try:  # registering is best-effort; the run + artifact are logged regardless
                    mlflow.register_model(mlflow.get_artifact_uri("model"), model_name)
                except Exception:
                    pass
        return True
    except Exception:
        return False


def latest_registered(model_name: str = MODEL_NAME) -> str | None:
    """Local download path of the latest registered model version's artifact, or None if
    MLflow/registry is unavailable (caller falls back to the local incumbent)."""
    mlflow = _mlflow()
    if mlflow is None:
        return None
    try:
        from mlflow.tracking import MlflowClient
        versions = MlflowClient().search_model_versions(f"name='{model_name}'")
        if not versions:
            return None
        latest = max(versions, key=lambda v: int(v.version))
        return mlflow.artifacts.download_artifacts(latest.source)
    except Exception:
        return None
