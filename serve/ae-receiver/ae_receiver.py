"""THESEUS — BlueROV2 AE edge receiver (theseus-uuv).

FastAPI service (port 54321) that speaks the same HTTP contract as the River-based
analytics:latest fleet nodes:
  GET  /health
  POST /stream-item  {topic_id, data:[{<ch>:v,...},...]}
  GET  /history

Inference: numpy + onnxruntime only (torch-free).  The Conv1d sequence autoencoder
takes a (1, 23, 64) standardised tensor and returns the reconstruction.  Anomaly
score = per-element MSE between reconstruction and input; flagged when score >= threshold.
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration — env-overridable so docker run -e works cleanly
# ---------------------------------------------------------------------------
ONNX_PATH   = os.getenv("ONNX_PATH",    "/model/uuv_seq_ae.onnx")
SCALER_PATH = os.getenv("SCALER_PATH",  "/model/scaler.json")
RESULTS_PATH = os.getenv("RESULTS_PATH", "/model/results.json")
MLFLOW_URI  = os.getenv("MLFLOW_URI",   "")
HISTORY_CAP = int(os.getenv("HISTORY_CAP", "100"))
WINDOW_SIZE = 64
N_CHANNELS  = 23

# ---------------------------------------------------------------------------
# Model state (loaded at startup)
# ---------------------------------------------------------------------------
_sess: ort.InferenceSession | None = None
_in_name: str = ""
_channels: list[str] = []
_mean: np.ndarray | None = None
_std:  np.ndarray | None = None
_threshold: float = 0.0
_buffer: list[list[float]] = []          # sliding raw sample buffer (rows = samples)
_history: deque = deque(maxlen=HISTORY_CAP)

app = FastAPI(title="theseus-uuv AE receiver")


# ---------------------------------------------------------------------------
# Startup: load ONNX + scaler
# ---------------------------------------------------------------------------
@app.on_event("startup")
def _load_model() -> None:
    global _sess, _in_name, _channels, _mean, _std, _threshold

    # --- scaler ---
    scaler = json.loads(Path(SCALER_PATH).read_text())
    _channels  = scaler["channels"]
    _mean      = np.asarray(scaler["mean"],  dtype=np.float32)
    raw_std    = np.asarray(scaler["std"],   dtype=np.float32)
    _std       = np.where(raw_std < 1e-6, 1.0, raw_std)
    _threshold = float(scaler["threshold"])

    # results.json carries the shipped_default_threshold (more authoritative)
    try:
        results = json.loads(Path(RESULTS_PATH).read_text())
        _threshold = float(results.get("shipped_default_threshold", _threshold))
        # prefer results.json channel list (canonical order)
        _channels = results.get("channels", _channels)
    except Exception:
        pass  # scaler.json threshold is fine

    # --- ONNX session (single thread, CPU; negligible latency at W=64) ---
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    _sess    = ort.InferenceSession(ONNX_PATH, so, providers=["CPUExecutionProvider"])
    _in_name = _sess.get_inputs()[0].name

    print(f"[ae-receiver] loaded {ONNX_PATH}  |  threshold={_threshold:.6f}  "
          f"|  channels={len(_channels)}  |  window={WINDOW_SIZE}")


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------
def _standardize(window_raw: np.ndarray) -> np.ndarray:
    """window_raw: (C, W) raw  ->  (C, W) standardised fp32."""
    return ((window_raw - _mean[:, None]) / _std[:, None]).astype(np.float32)


def _run_ae(std_window: np.ndarray) -> tuple[float, float, str]:
    """
    Run one (C, W) standardised window through the AE.

    Returns:
        score        — mean reconstruction MSE (anomaly score)
        display      — score mapped to [0,1] for the UI
        top_channel  — channel name with highest per-channel MSE (explainability)
    """
    x    = std_window[None, :, :].astype(np.float32)    # (1, C, W)
    recon = _sess.run(None, {_in_name: x})[0]           # (1, C, W)
    sq_err = (recon - x) ** 2                            # (1, C, W)
    score  = float(sq_err.mean())

    # per-channel mean squared error -> top explainability channel
    ch_mse = sq_err[0].mean(axis=1)                     # (C,)
    top_ch = _channels[int(ch_mse.argmax())]

    # map to [0,1]: score/(score+threshold) gives smooth 0.5 at threshold
    display = float(score / (score + _threshold)) if (score + _threshold) > 0 else 0.0

    return score, display, top_ch


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class StreamItem(BaseModel):
    topic_id: str
    data: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status":    "ok",
        "model":     "theseus-uuv",
        "framework": "onnx-autoencoder",
        "n_channels": N_CHANNELS,
        "window":    WINDOW_SIZE,
        "threshold": _threshold,
        "mlflow_uri": MLFLOW_URI,
    }


@app.post("/stream-item")
def stream_item(item: StreamItem) -> Dict[str, Any]:
    """Accept one or more telemetry records; buffer them; score when buffer full."""
    global _buffer

    last_score: Optional[float] = None
    window_full = False

    for record in item.data:
        # Build ordered 23-channel row; fill missing with channel mean (training imputation).
        row: list[float] = []
        for i, ch in enumerate(_channels):
            val = record.get(ch)
            if val is None:
                val = float(_mean[i])          # impute with training mean
            row.append(float(val))
        _buffer.append(row)

        # Keep only the most recent WINDOW_SIZE rows (sliding window, stride=1)
        if len(_buffer) > WINDOW_SIZE:
            _buffer = _buffer[-WINDOW_SIZE:]

        if len(_buffer) == WINDOW_SIZE:
            window_full = True
            raw = np.asarray(_buffer, dtype=np.float32).T   # (C, W)
            std = _standardize(raw)
            score, display, top_ch = _run_ae(std)
            flagged = score >= _threshold
            last_score = score

            _history.append({
                "timestamp":           time.time(),
                "active_anomaly_score": display,    # [0,1] display value for fleet API compat
                "raw_score":           score,
                "flagged":             flagged,
                "top_channel":         top_ch,
            })

    return {
        "status":      "buffered",
        "window_full": window_full,
        "last_score":  last_score,
    }


@app.get("/history", response_model=List[Dict[str, Any]])
def get_history() -> List[Dict[str, Any]]:
    return list(_history)
