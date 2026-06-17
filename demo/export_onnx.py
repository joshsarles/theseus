#!/usr/bin/env python3
"""THESEUS — ONNX export pipeline for edge inference (Raspberry Pi 5, 4 GB, CPU-only).

Exports:
  1. CBM regressor (sklearn GradientBoostingRegressor -> skl2onnx)
  2. MetroPT-3 autoencoder (PyTorch nn.Sequential -> torch.onnx.export)

Writes .onnx files to models/onnx/ and verifies numerical parity between the
original model and the ONNX runtime output on real held-out inputs.

Usage:
    cd /path/to/Theseus
    python3 demo/export_onnx.py

All paths are resolved relative to this file's repo root — portable.
"""
from __future__ import annotations

import csv
import json
import os
import pickle
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent       # demo/
ROOT = HERE.parent                           # repo root
ONNX_DIR = ROOT / "models" / "onnx"
ONNX_DIR.mkdir(parents=True, exist_ok=True)

CBM_REGISTRY  = HERE / "registry" / "theseus-cbm"
AE_REGISTRY   = HERE / "registry" / "theseus-ae"
CBM_DATA      = HERE / "data" / "staged.csv"
METRO_DATA    = ROOT / "ingest" / "out" / "metropt.csv"

PARITY_RTOL   = 1e-3   # relative tolerance for output parity assertion
PARITY_ATOL   = 1e-4   # absolute tolerance (handles near-zero outputs)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _latest(registry: Path) -> Path:
    vs = sorted(
        (p for p in registry.glob("v*") if p.name[1:].isdigit()),
        key=lambda p: int(p.name[1:]),
    )
    if not vs:
        raise FileNotFoundError(f"No versions found in {registry}")
    return vs[-1]


def _file_size_kb(path: Path) -> float:
    return path.stat().st_size / 1024


def _banner(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _parity_check(name: str, orig: np.ndarray, onnx_out: np.ndarray) -> bool:
    """Assert close, print max absolute diff, return pass/fail."""
    max_diff = float(np.max(np.abs(orig - onnx_out)))
    close = np.allclose(orig, onnx_out, rtol=PARITY_RTOL, atol=PARITY_ATOL)
    status = "PASS" if close else "FAIL"
    print(f"  [{status}] {name} parity — max abs diff = {max_diff:.2e}  "
          f"(rtol={PARITY_RTOL}, atol={PARITY_ATOL})")
    if not close:
        print(f"  !!! PARITY FAILURE — outputs diverge beyond tolerance !!!")
    return close


def _latency_ms(session, inputs: dict, n_reps: int = 200) -> tuple[float, float, float]:
    """Return (median_ms, p95_ms, p99_ms) over n_reps warm runs."""
    # warm-up
    for _ in range(10):
        session.run(None, inputs)
    times = []
    for _ in range(n_reps):
        t0 = time.perf_counter()
        session.run(None, inputs)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p50 = times[n_reps // 2]
    p95 = times[int(n_reps * 0.95)]
    p99 = times[int(n_reps * 0.99)]
    return p50, p95, p99


# ─────────────────────────────────────────────────────────────────────────────
# 1. CBM Regressor — sklearn -> ONNX via skl2onnx
# ─────────────────────────────────────────────────────────────────────────────

def export_cbm() -> dict:
    import onnxruntime as ort
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    _banner("CBM Regressor (sklearn GradientBoostingRegressor -> ONNX)")

    vdir = _latest(CBM_REGISTRY)
    meta = json.loads((vdir / "meta.json").read_text())
    print(f"  source : {vdir.relative_to(ROOT)}  (framework={meta['framework']})")
    print(f"  target : {meta['target']}")
    print(f"  n_feat : {len(meta['features'])}")
    print(f"  train RMSE: {meta['rmse']}")

    if meta["framework"] != "sklearn":
        raise RuntimeError(
            f"CBM registry v{meta['version']} uses '{meta['framework']}', "
            "not sklearn — re-run demo/retrain.py to get a sklearn model."
        )

    # Load model
    model = pickle.loads((vdir / "model.bin").read_bytes())
    n_features = len(meta["features"])

    # Export to ONNX
    # skl2onnx needs the input type declared.  Float32 is correct for Pi inference.
    initial_type = [("float_input", FloatTensorType([None, n_features]))]
    onnx_model = convert_sklearn(model, initial_types=initial_type, target_opset=17)

    out_path = ONNX_DIR / "cbm_regressor.onnx"
    with open(out_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    size_kb = _file_size_kb(out_path)
    print(f"  exported -> {out_path.relative_to(ROOT)}  ({size_kb:.1f} KB)")

    # ── Build a real input batch from the held-out test rows ──────────────────
    import random
    rows = list(csv.DictReader(CBM_DATA.open()))
    feats = meta["features"]
    target = meta["target"]
    # Reproduce the same shuffle as retrain.py so we use TRUE test rows
    random.Random(316).shuffle(rows)
    cut = int(len(rows) * 0.8)
    test_rows = rows[cut:]
    # Take first 64 test rows as our parity batch
    sample = test_rows[:64]
    X_test = np.array([[float(r[c]) for c in feats] for r in sample], dtype=np.float32)
    y_test = np.array([float(r[target]) for r in sample], dtype=np.float32)

    # Original sklearn prediction
    orig_pred = model.predict(X_test).astype(np.float32)

    # ONNX prediction
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    onnx_pred = sess.run(None, {input_name: X_test})[0].flatten().astype(np.float32)

    parity_ok = _parity_check("CBM regressor", orig_pred, onnx_pred)

    # ── Latency (single-sample, Pi-realistic) ────────────────────────────────
    single_in = X_test[:1]
    p50, p95, p99 = _latency_ms(sess, {input_name: single_in})
    print(f"  latency (1 sample, {200} reps): P50={p50:.2f}ms  P95={p95:.2f}ms  P99={p99:.2f}ms")

    # ── Dynamic quantization (int8) ───────────────────────────────────────────
    # Quantize via onnxruntime quantization
    quant_path = ONNX_DIR / "cbm_regressor_int8.onnx"
    _quantize_dynamic(out_path, quant_path, weight_type="uint8")
    quant_size_kb = _file_size_kb(quant_path)
    print(f"  int8 quantized -> {quant_path.relative_to(ROOT)}  ({quant_size_kb:.1f} KB)")

    sess_q = ort.InferenceSession(str(quant_path), providers=["CPUExecutionProvider"])
    quant_pred = sess_q.run(None, {input_name: single_in})[0].flatten()
    quant_diff = float(abs(float(quant_pred[0]) - float(sess.run(None, {input_name: single_in})[0].flatten()[0])))
    p50q, p95q, p99q = _latency_ms(sess_q, {input_name: single_in})
    print(f"  int8 latency (1 sample): P50={p50q:.2f}ms  P95={p95q:.2f}ms")
    print(f"  int8 vs fp32 output diff (1 sample): {quant_diff:.2e}")

    return {
        "model": "cbm_regressor",
        "source_framework": "sklearn",
        "onnx_path": str(out_path.relative_to(ROOT)),
        "onnx_size_kb": round(size_kb, 1),
        "int8_path": str(quant_path.relative_to(ROOT)),
        "int8_size_kb": round(quant_size_kb, 1),
        "parity_ok": parity_ok,
        "parity_max_abs_diff": float(np.max(np.abs(orig_pred - onnx_pred))),
        "latency_p50_ms": round(p50, 3),
        "latency_p95_ms": round(p95, 3),
        "latency_p99_ms": round(p99, 3),
        "int8_latency_p50_ms": round(p50q, 3),
        "int8_latency_p95_ms": round(p95q, 3),
        "int8_vs_fp32_output_diff": round(quant_diff, 6),
        "train_rmse": meta["rmse"],
        "n_features": n_features,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. MetroPT-3 Autoencoder — PyTorch -> ONNX via torch.onnx.export
# ─────────────────────────────────────────────────────────────────────────────

def export_autoencoder() -> dict:
    import torch
    import torch.nn as nn
    import onnxruntime as ort

    _banner("MetroPT-3 Autoencoder (PyTorch -> ONNX)")

    vdir = _latest(AE_REGISTRY)
    meta = json.loads((vdir / "meta.json").read_text())
    scaler = json.loads((vdir / "scaler.json").read_text())

    print(f"  source : {vdir.relative_to(ROOT)}  (arch={meta['arch']})")
    print(f"  ROC-AUC: {meta['roc_auc']}  recall={meta['recall']}  FAR={meta['false_alarm_rate']}")

    mean = scaler["mean"]
    std  = scaler["std"]
    feats = scaler["features"]
    d = len(feats)
    h1 = max(2, d // 2)
    h2 = max(2, d // 4)

    # Reconstruct the exact same architecture as autoencoder.py
    ae = nn.Sequential(
        nn.Linear(d, h1), nn.ReLU(), nn.Linear(h1, h2), nn.ReLU(),
        nn.Linear(h2, h1), nn.ReLU(), nn.Linear(h1, d),
    )
    ae.load_state_dict(torch.load(vdir / "autoencoder.pt", map_location="cpu", weights_only=True))
    ae.eval()

    # Build a real input batch from metropt data (standardized, same as training)
    raw_rows = list(csv.DictReader(METRO_DATA.open()))
    X_raw = [[float(r[c]) for c in feats] for r in raw_rows]
    # Standardize exactly as autoencoder.py does
    Z = [[(x - mean[j]) / std[j] for j, x in enumerate(row)] for row in X_raw]
    # Use 128-sample batch spanning normal + anomaly rows for parity check
    sample_idx = list(range(0, min(128, len(Z))))
    X_sample = np.array([Z[i] for i in sample_idx], dtype=np.float32)

    # Original PyTorch output
    with torch.no_grad():
        orig_out = ae(torch.tensor(X_sample)).numpy()

    # Export to ONNX with dynamic batch axis.
    # dynamo=False selects the stable TorchScript-based legacy exporter (torch 2.10+).
    dummy_input = torch.zeros(1, d, dtype=torch.float32)
    out_path = ONNX_DIR / "autoencoder.onnx"
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        torch.onnx.export(
            ae,
            dummy_input,
            str(out_path),
            dynamo=False,
            input_names=["input"],
            output_names=["reconstruction"],
            dynamic_axes={"input": {0: "batch_size"}, "reconstruction": {0: "batch_size"}},
            opset_version=17,
            do_constant_folding=True,
        )
    size_kb = _file_size_kb(out_path)
    print(f"  exported -> {out_path.relative_to(ROOT)}  ({size_kb:.1f} KB)")

    # ONNX parity check
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    onnx_out = sess.run(None, {"input": X_sample})[0]
    parity_ok = _parity_check("Autoencoder", orig_out, onnx_out)

    # Latency — single sample, Pi-realistic
    single_in = X_sample[:1]
    p50, p95, p99 = _latency_ms(sess, {"input": single_in})
    print(f"  latency (1 sample, 200 reps): P50={p50:.2f}ms  P95={p95:.2f}ms  P99={p99:.2f}ms")

    # Dynamic quantization (int8 weights)
    quant_path = ONNX_DIR / "autoencoder_int8.onnx"
    _quantize_dynamic(out_path, quant_path, weight_type="uint8")
    quant_size_kb = _file_size_kb(quant_path)
    print(f"  int8 quantized -> {quant_path.relative_to(ROOT)}  ({quant_size_kb:.1f} KB)")

    sess_q = ort.InferenceSession(str(quant_path), providers=["CPUExecutionProvider"])
    quant_out = sess_q.run(None, {"input": single_in})[0]
    fp32_out  = sess.run(None, {"input": single_in})[0]
    quant_diff = float(np.max(np.abs(quant_out - fp32_out)))
    p50q, p95q, p99q = _latency_ms(sess_q, {"input": single_in})
    print(f"  int8 latency (1 sample): P50={p50q:.2f}ms  P95={p95q:.2f}ms")
    print(f"  int8 vs fp32 recon diff (1 sample, max abs): {quant_diff:.2e}")

    return {
        "model": "autoencoder",
        "source_framework": "pytorch",
        "arch": meta["arch"],
        "onnx_path": str(out_path.relative_to(ROOT)),
        "onnx_size_kb": round(size_kb, 1),
        "int8_path": str(quant_path.relative_to(ROOT)),
        "int8_size_kb": round(quant_size_kb, 1),
        "parity_ok": parity_ok,
        "parity_max_abs_diff": float(np.max(np.abs(orig_out - onnx_out))),
        "latency_p50_ms": round(p50, 3),
        "latency_p95_ms": round(p95, 3),
        "latency_p99_ms": round(p99, 3),
        "int8_latency_p50_ms": round(p50q, 3),
        "int8_latency_p95_ms": round(p95q, 3),
        "int8_vs_fp32_recon_diff": round(quant_diff, 6),
        "roc_auc": meta["roc_auc"],
        "n_features": d,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quantization helper (dynamic, weight-only)
# ─────────────────────────────────────────────────────────────────────────────

def _quantize_dynamic(fp32_path: Path, out_path: Path, weight_type: str = "uint8") -> None:
    """Dynamic quantization: quantizes weights to int8/uint8, activations remain float.

    Normalises the ONNX model's opset_import before quantizing: skl2onnx can emit
    duplicate empty-domain entries which confuse onnxruntime's get_opset_version check.
    We de-duplicate, keeping the entry with the highest version.
    """
    import onnx
    from onnxruntime.quantization import quantize_dynamic, QuantType

    # Load, de-duplicate opset entries, save to a temp file, then quantize
    model = onnx.load(str(fp32_path))
    # Collect best version per domain (empty string == ai.onnx per spec)
    best: dict[str, int] = {}
    for op in model.opset_import:
        key = op.domain  # '' or 'ai.onnx.ml' etc.
        best[key] = max(best.get(key, 0), op.version)
    del model.opset_import[:]
    for domain, version in best.items():
        entry = model.opset_import.add()
        entry.domain = domain
        entry.version = version

    # Write normalised model to a sidecar, quantize from it
    norm_path = fp32_path.with_suffix(".norm.onnx")
    onnx.save(model, str(norm_path))
    try:
        qtype = QuantType.QUInt8 if weight_type == "uint8" else QuantType.QInt8
        quantize_dynamic(str(norm_path), str(out_path), weight_type=qtype)
    finally:
        norm_path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    print("THESEUS — ONNX Export Pipeline (edge inference / Raspberry Pi 5 4 GB)")
    print(f"Output dir: {ONNX_DIR.relative_to(ROOT)}")

    results = {}
    all_pass = True

    try:
        cbm_result = export_cbm()
        results["cbm_regressor"] = cbm_result
        if not cbm_result["parity_ok"]:
            all_pass = False
    except Exception as e:
        print(f"\n[FAIL] CBM export error: {e}")
        import traceback; traceback.print_exc()
        all_pass = False

    try:
        ae_result = export_autoencoder()
        results["autoencoder"] = ae_result
        if not ae_result["parity_ok"]:
            all_pass = False
    except Exception as e:
        print(f"\n[FAIL] Autoencoder export error: {e}")
        import traceback; traceback.print_exc()
        all_pass = False

    # Write results summary
    summary_path = ONNX_DIR / "export_results.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\n  results -> {summary_path.relative_to(ROOT)}")

    # Final verdict
    print(f"\n{'='*60}")
    print(f"  OVERALL: {'PASS' if all_pass else 'FAIL'}")
    if results:
        for name, r in results.items():
            p = "PASS" if r["parity_ok"] else "FAIL"
            print(f"  [{p}] {name}  fp32={r['onnx_size_kb']}KB  int8={r['int8_size_kb']}KB  "
                  f"P50={r['latency_p50_ms']}ms  max_diff={r['parity_max_abs_diff']:.2e}")
    print(f"{'='*60}\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
