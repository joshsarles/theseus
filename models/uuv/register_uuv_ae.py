#!/usr/bin/env python3
"""Register theseus-uuv in Node-3 MLflow (http://localhost:5050) as @production.

Serving path: numpy + onnxruntime ONLY (no torch at inference time).
  - Loads models/onnx/uuv_seq_ae.onnx (fp32, exported from model.pt)
  - Standardizes (C,W) windows with scaler.json mean/std
  - Returns per-window MSE reconstruction-error anomaly score
  - Flags windows above the shipped default threshold (0.4176)

Registered model: theseus-uuv
Alias: @production

Run with:
  MLFLOW_TRACKING_URI=http://localhost:5050 \\
  /Users/force/Developer/Theseus/deploy/mlflow/.venv312/bin/python \\
  /Users/force/Developer/Theseus/models/uuv/register_uuv_ae.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import mlflow
import mlflow.pyfunc
import numpy as np

# ----------------------------------------------------------------------------- paths
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCALER_PATH = HERE / "scaler.json"
ONNX_PATH = ROOT / "models" / "onnx" / "uuv_seq_ae.onnx"
RESULTS_PATH = HERE / "results.json"
META_PATH = HERE / "meta.json"

TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050")
MODEL_NAME = "theseus-uuv"
ALIAS = "production"

# ----------------------------------------------------------------------------- pyfunc wrapper
class UUVAnomalyScorer(mlflow.pyfunc.PythonModel):
    """MLflow pyfunc wrapping the theseus-uuv ONNX autoencoder.

    Input contract (predict):
      model_input: dict with key "windows"
        - numpy array of shape (N, C, W) = (N, 23, 64), float32, pre-standardized
        - OR numpy array of shape (N, C, W), raw (un-standardized) — set standardize=True in context

        Simplest call:
          scorer.predict(ctx, {"windows": raw_windows_NCW, "standardize": True})

      Returns: dict
        "scores"    float32 array (N,)  — per-window MSE reconstruction error
        "flagged"   bool array   (N,)  — score > threshold
        "threshold" float        scalar — operating threshold
    """

    def load_context(self, context: mlflow.pyfunc.PythonModelContext):
        import onnxruntime as ort
        scaler_file = context.artifacts["scaler"]
        onnx_file = context.artifacts["onnx_model"]
        sc = json.loads(Path(scaler_file).read_text())
        self.channels = sc["channels"]
        self.mean = np.asarray(sc["mean"], dtype=np.float32)  # (C,)
        _std = np.asarray(sc["std"], dtype=np.float32)
        self.std = np.where(_std < 1e-6, 1.0, _std)           # (C,)
        self.W = int(sc["window"])
        self.threshold = float(sc["threshold"])
        self.target_far = float(sc.get("target_far", 0.02))

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(
            onnx_file, so, providers=["CPUExecutionProvider"]
        )
        self.in_name = self.sess.get_inputs()[0].name

    def _standardize(self, windows: np.ndarray) -> np.ndarray:
        """windows: (N, C, W) raw -> standardized (N, C, W) float32."""
        w = windows.astype(np.float32)
        return (w - self.mean[None, :, None]) / self.std[None, :, None]

    def predict(self, context, model_input):
        if isinstance(model_input, dict):
            windows = np.asarray(model_input["windows"], dtype=np.float32)
            do_std = bool(model_input.get("standardize", False))
        else:
            # pandas DataFrame fallback: expect flattened (N, C*W) with optional first col 'standardize'
            windows = np.asarray(model_input, dtype=np.float32)
            do_std = False

        if windows.ndim == 2:
            # (C, W) single window — wrap
            windows = windows[None, :, :]
        if windows.ndim != 3:
            raise ValueError(f"Expected (N,C,W) or (C,W) input, got shape {windows.shape}")

        if do_std:
            windows = self._standardize(windows)

        x = windows.astype(np.float32)
        recon = self.sess.run(None, {self.in_name: x})[0]   # (N, C, W)
        scores = ((recon - x) ** 2).mean(axis=(1, 2)).astype(np.float32)  # (N,)
        flagged = scores > self.threshold

        return {
            "scores": scores,
            "flagged": flagged,
            "threshold": float(self.threshold),
        }


# ----------------------------------------------------------------------------- registration
def main():
    mlflow.set_tracking_uri(TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    results = json.loads(RESULTS_PATH.read_text())
    meta = json.loads(META_PATH.read_text())
    sc = json.loads(SCALER_PATH.read_text())

    overall = results["eval_overall_synthetic"]
    edge = results["edge"]["onnx"]

    # Smoke-test the ONNX before logging anything
    print(f"Smoke-testing ONNX at {ONNX_PATH} ...")
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    sess = ort.InferenceSession(str(ONNX_PATH), so, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    dummy = np.zeros((1, 23, 64), dtype=np.float32)
    recon = sess.run(None, {in_name: dummy})[0]
    recon_err = float(((recon - dummy) ** 2).mean())
    print(f"  smoke-test recon_err on zeros: {recon_err:.6f}  (expected ~0 for a well-trained AE)")

    # MLflow experiment
    exp_name = "uuv_ae_registration"
    try:
        exp_id = client.create_experiment(exp_name)
    except mlflow.exceptions.MlflowException:
        exp_id = client.get_experiment_by_name(exp_name).experiment_id

    print(f"\nLogging to MLflow experiment '{exp_name}' (id={exp_id}) ...")
    with mlflow.start_run(experiment_id=exp_id, run_name="register-theseus-uuv") as run:
        # --- params ---
        mlflow.log_params({
            "model": meta["model"],
            "channels": meta["channels"],
            "window": meta["window"],
            "latent": meta["latent"],
            "arch": meta["arch"],
            "epochs": meta["epochs"],
            "seed": meta["seed"],
            "n_train_windows": meta["n_train_windows"],
            "framework": meta["framework"],
            "dataset": "BlueROV2 Zenodo 10.5281/zenodo.17360027 CC-BY-4.0",
            "framing": "B — UUV own-systems (battery/thrusters/attitude/IMU/pressure)",
            "eval_method": "per-recording in-situ threshold (cold-start deployment mirror)",
        })

        # --- overall eval metrics ---
        mlflow.log_metrics({
            "eval_precision":        overall["precision"],
            "eval_recall":           overall["recall"],
            "eval_f1":               overall["f1"],
            "eval_roc_auc":          overall["roc_auc"],
            "eval_false_alarm_rate": overall["false_alarm_rate"],
            "eval_tp":               overall["tp"],
            "eval_fp":               overall["fp"],
            "eval_fn":               overall["fn"],
            "eval_tn":               overall["tn"],
        })

        # --- per-fault breakdown metrics ---
        for fault, fm in results["eval_per_synthetic_fault"].items():
            mlflow.log_metrics({
                f"fault_{fault}_precision": fm["precision"],
                f"fault_{fault}_recall":    fm["recall"],
                f"fault_{fault}_f1":        fm["f1"],
                f"fault_{fault}_roc_auc":   fm["roc_auc"],
            })

        # --- threshold + edge ---
        mlflow.log_metrics({
            "shipped_default_threshold": results["shipped_default_threshold"],
            "insitu_threshold_mean":     results["insitu_threshold_mean"],
            "target_far":                results["target_far"],
            "onnx_fp32_kb":              edge["fp32_kb"],
            "onnx_latency_ms_1thread":   edge["single_window_latency_ms_1thread"],
            "onnx_torch_vs_onnx_max_abs_err": edge["torch_vs_onnx_recon_err_max_abs"],
        })

        # --- log the pyfunc model with ONNX + scaler as artifacts ---
        artifacts = {
            "scaler": str(SCALER_PATH),
            "onnx_model": str(ONNX_PATH),
        }

        conda_env = {
            "channels": ["defaults", "conda-forge"],
            "dependencies": [
                "python=3.12",
                "pip",
                {"pip": ["mlflow", "numpy", "onnxruntime"]},
            ],
            "name": "theseus-uuv-env",
        }

        model_info = mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=UUVAnomalyScorer(),
            artifacts=artifacts,
            conda_env=conda_env,
            registered_model_name=MODEL_NAME,
        )

        run_id = run.info.run_id
        print(f"  run_id: {run_id}")
        print(f"  model_uri: {model_info.model_uri}")

    # --- set @production alias on the latest version ---
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    latest = sorted(versions, key=lambda v: int(v.version))[-1]
    client.set_registered_model_alias(MODEL_NAME, ALIAS, latest.version)
    print(f"\nRegistered '{MODEL_NAME}' version {latest.version} as @{ALIAS}")

    # --- verify: load from alias and score a sample window ---
    print(f"\nVerifying models:/{MODEL_NAME}@{ALIAS} ...")
    loaded = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{ALIAS}")

    # Build a sample window: zeros (nominal-ish after standardization)
    C, W = 23, 64
    mean = np.asarray(sc["mean"], dtype=np.float32)
    std_arr = np.asarray(sc["std"], dtype=np.float32)
    std_arr = np.where(std_arr < 1e-6, 1.0, std_arr)

    # Score 3 windows: zeros raw (will standardize), a nominal-ish window, a spike window
    raw_zeros = np.zeros((3, C, W), dtype=np.float32)
    # nominal window: values at mean (will produce ~0 after standardization -> low recon error)
    raw_zeros[1] = mean[:, None]
    # fault window: large spike on thruster channels
    raw_zeros[2, 13:19, 32:] = mean[13:19, None] + 5 * std_arr[13:19, None]

    result = loaded.predict({"windows": raw_zeros, "standardize": True})
    scores = result["scores"]
    flagged = result["flagged"]
    threshold = result["threshold"]

    print(f"  threshold: {threshold:.6f}")
    print(f"  window[0] score (all-zeros raw):         {scores[0]:.6f}  flagged={flagged[0]}")
    print(f"  window[1] score (mean-value raw, nominal):{scores[1]:.6f}  flagged={flagged[1]}")
    print(f"  window[2] score (thruster spike):         {scores[2]:.6f}  flagged={flagged[2]}")

    print(f"\nSUCCESS — models:/{MODEL_NAME}@{ALIAS} loads and scores correctly.")
    print(f"\nEval summary (overall synthetic faults, n={overall['tp']+overall['fn']+overall['fp']+overall['tn']}):")
    print(f"  F1={overall['f1']:.4f}  AUC-ROC={overall['roc_auc']:.4f}  "
          f"Precision={overall['precision']:.4f}  Recall={overall['recall']:.4f}  FAR={overall['false_alarm_rate']:.4f}")
    print(f"  Threshold: shipped={results['shipped_default_threshold']:.6f}  "
          f"insitu_mean={results['insitu_threshold_mean']:.5f}")
    print(f"  Edge: fp32 ONNX {edge['fp32_kb']:.1f} KB  latency {edge['single_window_latency_ms_1thread']:.4f} ms/window (1 thread)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
