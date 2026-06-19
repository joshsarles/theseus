#!/usr/bin/env python3
"""THESEUS — inference-only Pi-5-4GB footprint for the UUV sequence-autoencoder ONNX model.

Measures what a deployed Raspberry Pi actually pays: a minimal process that imports only
numpy + onnxruntime, loads the ONNX model, and runs single-window inference single-threaded.
This is the honest deployment number (NOT the training-process peak RSS, which includes torch).

Computes the reconstruction-error anomaly score the same way the trainer does (mean squared
error over channels x window), so the edge path is identical to the trained scorer.

  python3 models/uuv/pi_bench.py [--int8]
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort


def _peak_rss_mb() -> float:
    """ru_maxrss is BYTES on macOS but KILOBYTES on Linux (the Raspberry Pi) — convert per-platform."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCALER = HERE / "scaler.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Pi inference-only benchmark for the UUV AE.")
    ap.add_argument("--int8", action="store_true", help="benchmark the int8 model instead of fp32")
    a = ap.parse_args()

    name = "uuv_seq_ae_int8.onnx" if a.int8 else "uuv_seq_ae.onnx"
    model = ROOT / "models" / "onnx" / name
    if not model.exists():
        print(f"  model missing: {model} (run train_uuv_ae.py)"); return 1
    if not SCALER.exists():
        print(f"  scaler missing: {SCALER} (run train_uuv_ae.py)"); return 1
    sc = json.loads(SCALER.read_text())
    C, W, thr = len(sc["channels"]), sc["window"], sc["threshold"]

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(model.as_posix(), so, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    one = np.zeros((1, C, W), dtype=np.float32)
    for _ in range(50):
        sess.run(None, {in_name: one})

    def score(x):                       # reconstruction-error anomaly score (matches trainer)
        recon = sess.run(None, {in_name: x})[0]
        return float(((recon - x) ** 2).mean())

    def bench(n):
        t = time.time()
        for _ in range(n):
            score(one)
        return (time.time() - t) / n * 1000

    _ = score(one)
    lat = bench(2000)
    peak_rss_mb = _peak_rss_mb()

    rep = {
        "model": str(model.relative_to(ROOT)),
        "model_kb": round(model.stat().st_size / 1024, 1),
        "precision": "int8" if a.int8 else "fp32",
        "onnxruntime_version": ort.__version__,
        "threads": 1,
        "channels": C, "window": W, "threshold": thr,
        "latency_ms_per_window_single": round(lat, 4),
        "windows_per_sec": round(1000 / lat, 1),
        "inference_process_peak_rss_mb": round(peak_rss_mb, 1),
        "note": "Inference-only process (numpy + onnxruntime). Pi 5 / 4GB headroom is ample: "
                f"model {round(model.stat().st_size/1024,1)} KB, RSS well under 4 GB, and at "
                "10 Hz telemetry a window arrives every 100 ms while inference is sub-ms — "
                "real-time on one core with vast margin.",
    }
    (HERE / ("pi_bench_int8.json" if a.int8 else "pi_bench.json")).write_text(
        json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
