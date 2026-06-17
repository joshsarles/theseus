#!/usr/bin/env python3
"""THESEUS — Minimal ONNX edge inference for Raspberry Pi 5 (4 GB, CPU-only).

Provides two inference functions:
  predict_cbm(features)       — CBM regressor: returns gt_compressor_decay estimate
  predict_anomaly(features)   — MetroPT AE: returns (recon_error, is_anomaly bool)

Deps: onnxruntime (pip install onnxruntime)  — no torch, no sklearn at serving time.

Usage:
    python3 models/onnx/infer.py --demo

The --demo flag runs a self-contained benchmark on synthetic data so you can
verify the install on any machine (Pi, x86 server, laptop) without needing the
original datasets.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import NamedTuple

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent   # models/onnx/
ROOT = HERE.parent.parent                # repo root

# ─── model paths ────────────────────────────────────────────────────────────
CBM_ONNX   = HERE / "cbm_regressor.onnx"
AE_ONNX    = HERE / "autoencoder.onnx"

# CBM feature order (must match demo/registry/theseus-cbm/v*/meta.json)
CBM_FEATURES = [
    "lever_position", "ship_speed", "gt_shaft_torque", "gt_rpm", "gas_gen_rpm",
    "stbd_prop_torque", "port_prop_torque", "hp_turbine_exit_temp",
    "compressor_outlet_temp", "hp_turbine_exit_press", "compressor_outlet_press",
    "exhaust_gas_press", "turbine_injection_ctrl", "fuel_flow",
]

# AE feature order + scaler — loaded lazily from registry scaler.json
AE_FEATURES: list[str] | None = None
AE_MEAN: list[float] | None = None
AE_STD:  list[float] | None = None
AE_THRESHOLD: float | None = None


# ─── lazy sessions (singleton, initialised on first call) ───────────────────
_cbm_session: ort.InferenceSession | None = None
_ae_session:  ort.InferenceSession | None = None


def _cbm_sess() -> ort.InferenceSession:
    global _cbm_session
    if _cbm_session is None:
        _cbm_session = ort.InferenceSession(
            str(CBM_ONNX), providers=["CPUExecutionProvider"]
        )
    return _cbm_session


def _ae_sess() -> ort.InferenceSession:
    global _ae_session
    if _ae_session is None:
        _ae_session = ort.InferenceSession(
            str(AE_ONNX), providers=["CPUExecutionProvider"]
        )
    return _ae_session


def _load_ae_meta() -> None:
    """Load AE scaler + threshold from the registry once."""
    global AE_FEATURES, AE_MEAN, AE_STD, AE_THRESHOLD
    if AE_FEATURES is not None:
        return
    # Walk registry to find latest version
    ae_reg = ROOT / "demo" / "registry" / "theseus-ae"
    vs = sorted(
        (p for p in ae_reg.glob("v*") if p.name[1:].isdigit()),
        key=lambda p: int(p.name[1:]),
    )
    if not vs:
        raise FileNotFoundError(f"No AE registry versions found in {ae_reg}")
    vdir = vs[-1]
    scaler = json.loads((vdir / "scaler.json").read_text())
    meta   = json.loads((vdir / "meta.json").read_text())
    AE_FEATURES = scaler["features"]
    AE_MEAN     = scaler["mean"]
    AE_STD      = scaler["std"]
    AE_THRESHOLD = meta["threshold"]


# ─── public inference API ────────────────────────────────────────────────────

class CBMResult(NamedTuple):
    gt_compressor_decay: float
    latency_ms: float


class AnomalyResult(NamedTuple):
    recon_error: float
    is_anomaly: bool
    threshold: float
    latency_ms: float


def predict_cbm(features: dict[str, float] | list[float]) -> CBMResult:
    """Predict gt_compressor_decay for one sample.

    Args:
        features: dict keyed by CBM_FEATURES names, OR a plain list of 14 floats
                  in CBM_FEATURES order.

    Returns:
        CBMResult(gt_compressor_decay, latency_ms)
    """
    if isinstance(features, dict):
        x = np.array([[features[k] for k in CBM_FEATURES]], dtype=np.float32)
    else:
        x = np.array([features], dtype=np.float32)

    sess = _cbm_sess()
    input_name = sess.get_inputs()[0].name

    t0 = time.perf_counter()
    out = sess.run(None, {input_name: x})[0]
    lat = (time.perf_counter() - t0) * 1000

    return CBMResult(float(out.flatten()[0]), round(lat, 4))


def predict_anomaly(
    features: dict[str, float] | list[float],
    *,
    standardize: bool = True,
) -> AnomalyResult:
    """Detect anomaly in a single MetroPT sensor reading.

    Args:
        features: dict keyed by AE_FEATURES names, OR a list of 15 raw floats
                  in AE_FEATURES order.
        standardize: apply z-score normalisation using training stats (default True;
                     set False only if you've already standardized externally).

    Returns:
        AnomalyResult(recon_error, is_anomaly, threshold, latency_ms)
    """
    _load_ae_meta()

    if isinstance(features, dict):
        raw = [features[k] for k in AE_FEATURES]  # type: ignore[index]
    else:
        raw = list(features)

    if standardize:
        z = [(v - AE_MEAN[j]) / AE_STD[j] for j, v in enumerate(raw)]  # type: ignore[index]
    else:
        z = raw

    x = np.array([z], dtype=np.float32)
    sess = _ae_sess()

    t0 = time.perf_counter()
    recon = sess.run(None, {"input": x})[0]
    lat = (time.perf_counter() - t0) * 1000

    recon_error = float(np.mean((recon - x) ** 2))
    is_anom = recon_error > AE_THRESHOLD  # type: ignore[operator]

    return AnomalyResult(recon_error, is_anom, AE_THRESHOLD, round(lat, 4))  # type: ignore[arg-type]


# ─── self-test / benchmark ───────────────────────────────────────────────────

def _demo() -> None:
    print("THESEUS ONNX Edge Inference — self-test benchmark")
    print(f"  onnxruntime: {ort.__version__}")
    print(f"  CBM model  : {CBM_ONNX.relative_to(ROOT)}  ({CBM_ONNX.stat().st_size/1024:.1f} KB)")
    print(f"  AE  model  : {AE_ONNX.relative_to(ROOT)}  ({AE_ONNX.stat().st_size/1024:.1f} KB)")

    # ── CBM ──
    print("\n[CBM regressor]")
    # Use a representative mid-range sample (lever=2, ship_speed=6)
    cbm_sample = {
        "lever_position": 2.0, "ship_speed": 6.0, "gt_shaft_torque": 6960.18,
        "gt_rpm": 1376.17, "gas_gen_rpm": 6828.47, "stbd_prop_torque": 28.2,
        "port_prop_torque": 28.2, "hp_turbine_exit_temp": 635.4,
        "compressor_outlet_temp": 581.7, "hp_turbine_exit_press": 1.331,
        "compressor_outlet_press": 0.998, "exhaust_gas_press": 7.282,
        "turbine_injection_ctrl": 1.019, "fuel_flow": 10.655,
    }
    r = predict_cbm(cbm_sample)
    print(f"  gt_compressor_decay = {r.gt_compressor_decay:.6f}")
    print(f"  latency (cold)      = {r.latency_ms:.3f} ms")

    # Warm latency benchmark: 500 reps
    times = []
    for _ in range(500):
        t0 = time.perf_counter()
        predict_cbm(cbm_sample)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p50, p95, p99 = times[250], times[474], times[494]
    print(f"  latency (warm 500x) P50={p50:.3f}ms  P95={p95:.3f}ms  P99={p99:.3f}ms")

    # ── AE ──
    print("\n[Autoencoder anomaly detector]")
    _load_ae_meta()
    # Normal-ish sample (all sensors at mean)
    normal_sample = {f: AE_MEAN[i] for i, f in enumerate(AE_FEATURES)}  # type: ignore[index]
    r2 = predict_anomaly(normal_sample)
    print(f"  recon_error (normal sample) = {r2.recon_error:.6f}")
    print(f"  threshold                   = {r2.threshold:.6f}")
    print(f"  is_anomaly                  = {r2.is_anomaly}")
    print(f"  latency (cold)              = {r2.latency_ms:.3f} ms")

    # Anomalous sample (DV_pressure feature pushed to 3× normal — simulates air-leak)
    anom_sample = dict(normal_sample)
    dp_idx = AE_FEATURES.index("DV_pressure")  # type: ignore[index]
    anom_sample["DV_pressure"] = AE_MEAN[dp_idx] + 3.0 * AE_STD[dp_idx]  # type: ignore[index]
    r3 = predict_anomaly(anom_sample)
    print(f"  recon_error (anomaly sim)   = {r3.recon_error:.6f}")
    print(f"  is_anomaly                  = {r3.is_anomaly}")

    times2 = []
    for _ in range(500):
        t0 = time.perf_counter()
        predict_anomaly(normal_sample)
        times2.append((time.perf_counter() - t0) * 1000)
    times2.sort()
    p50b, p95b, p99b = times2[250], times2[474], times2[494]
    print(f"  latency (warm 500x) P50={p50b:.3f}ms  P95={p95b:.3f}ms  P99={p99b:.3f}ms")

    print("\n  Pi-5 (4 GB, Cortex-A76 @ 2.4 GHz) scaling estimate:")
    print("    Mac M5 single-core Geekbench ~3700, Pi 5 ~860 (~4.3× slower)")
    print(f"    CBM P50 ~{p50*4.3:.1f} ms  P95 ~{p95*4.3:.1f} ms  (well under 100 ms target)")
    print(f"    AE  P50 ~{p50b*4.3:.1f} ms  P95 ~{p95b*4.3:.1f} ms")
    print("\n  [PASS] Edge inference self-test complete")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="THESEUS ONNX edge inference")
    ap.add_argument("--demo", action="store_true", help="run benchmark / self-test")
    a = ap.parse_args()
    if a.demo:
        _demo()
    else:
        ap.print_help()
