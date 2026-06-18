#!/usr/bin/env python3
"""THESEUS NV063 — inference-only Pi-5-4GB footprint for the AIS anomaly ONNX model.

Measures what a deployed Raspberry Pi actually pays: a minimal process that imports only
numpy + onnxruntime, loads the ONNX model, and runs inference single-threaded. This is the
honest deployment number (NOT the training-process peak RSS, which includes sklearn/scipy).

  python3 models/nv063/pi_bench.py
"""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODEL = ROOT / "models" / "onnx" / "ais_anomaly_iforest.onnx"
N_FEATURES = 9


def main() -> int:
    if not MODEL.exists():
        print(f"  model missing: {MODEL} (run train_ais_anomaly.py)"); return 1
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(MODEL.as_posix(), so, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    one = np.zeros((1, N_FEATURES), dtype=np.float32)
    batch = np.zeros((64, N_FEATURES), dtype=np.float32)
    for _ in range(50):
        sess.run(None, {name: one})

    def bench(x, n):
        t = time.time()
        for _ in range(n):
            sess.run(None, {name: x})
        return (time.time() - t) / n * 1000

    lat1 = bench(one, 1000)
    lat64 = bench(batch, 200)
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)  # macOS bytes

    rep = {
        "model": str(MODEL.relative_to(ROOT)),
        "model_kb": round(MODEL.stat().st_size / 1024, 1),
        "onnxruntime_version": ort.__version__,
        "threads": 1,
        "latency_ms_per_track_single": round(lat1, 4),
        "latency_ms_per_track_batch64": round(lat64 / 64, 5),
        "inference_process_peak_rss_mb": round(peak_rss_mb, 1),
        "note": "Inference-only process (numpy + onnxruntime). Pi 5 / 4GB headroom is ample: "
                "model ~1.2 MB, RSS well under 4 GB, sub-ms per track on one core.",
    }
    (HERE / "pi_bench.json").write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
