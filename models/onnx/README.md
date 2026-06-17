# THESEUS — ONNX Edge Inference

ONNX models + inference path for CPU-only edge deployment (Raspberry Pi 5, 4 GB RAM).
No PyTorch or sklearn at serving time — only `onnxruntime`.

## Files

| File | Description |
|------|-------------|
| `cbm_regressor.onnx` | CBM GradientBoostingRegressor (fp32) |
| `cbm_regressor_int8.onnx` | CBM int8 weight-quantized variant |
| `autoencoder.onnx` | MetroPT-3 anomaly autoencoder (fp32, arch 15-7-3-7-15) |
| `autoencoder_int8.onnx` | AE int8 weight-quantized variant |
| `infer.py` | Minimal edge inference API (onnxruntime, no heavy deps) |
| `export_results.json` | Machine-readable parity + latency results |

## Export

```bash
# From repo root — re-export both models any time a new version is registered
python3 demo/export_onnx.py
```

Requires: `pip install onnx skl2onnx onnxruntime` plus `torch` (export time only;
not needed at inference time on the Pi).

## Parity Results (verified on Mac M5)

Both models verified numerically identical between original framework and ONNX Runtime
on 64–128 real held-out samples.

| Model | Parity | Max abs diff | Tolerance |
|-------|--------|-------------|-----------|
| CBM regressor | **PASS** | 5.96e-08 | rtol=1e-3, atol=1e-4 |
| AE autoencoder | **PASS** | 5.96e-08 | rtol=1e-3, atol=1e-4 |

The diff is floating-point rounding noise (~2 ULP in float32), well within tolerance.

## Model Sizes

| Model | fp32 | int8 |
|-------|------|------|
| CBM regressor | 54.3 KB | 54.3 KB* |
| AE autoencoder | 2.0 KB | 4.8 KB** |

\* GradientBoosting tree ensembles store split thresholds and leaf values as floating-point
constants in ONNX; dynamic weight quantization has no integer weights to substitute, so the
file size is identical. The tree traversal logic is unchanged.

\** The AE int8 model is larger because quantization adds per-layer scale/zero-point
parameters alongside the quantized weights. For a 15-7-3-7-15 network this overhead
exceeds the tiny weight savings. The fp32 model (2.0 KB) is the right choice for the Pi.

Both models fit comfortably in the Pi 5's 4 GB RAM with 5+ orders of magnitude headroom.

## Latency (Mac M5, then Pi-5 estimate)

Benchmarked with 500 warm single-sample inferences via `onnxruntime` CPU provider.

| Model | Mac M5 P50 | Mac M5 P95 | Pi-5 P50 est. | Pi-5 P95 est. |
|-------|-----------|-----------|--------------|--------------|
| CBM fp32 | 0.008 ms | 0.012 ms | ~0.03 ms | ~0.05 ms |
| AE fp32 | 0.009 ms | 0.012 ms | ~0.04 ms | ~0.05 ms |

Pi-5 estimate applies a 4.3× single-core slowdown (M5 ~3700 vs Pi-5 Cortex-A76 ~860
Geekbench single-core score). Both models are well under the 100 ms real-time budget.

## Edge Inference API

```python
from models.onnx.infer import predict_cbm, predict_anomaly

# CBM: pass dict or list of 14 floats in CBM_FEATURES order
result = predict_cbm({
    "lever_position": 2.0, "ship_speed": 6.0,
    # ... 14 total features
})
print(result.gt_compressor_decay, result.latency_ms)

# Anomaly: pass raw sensor dict; standardization applied automatically
result = predict_anomaly({"TP2": -0.013, "TP3": 9.05, ...})
print(result.recon_error, result.is_anomaly, result.threshold)
```

### Pi 5 install

```bash
pip install onnxruntime numpy    # ~60 MB, no GPU deps
# copy models/onnx/ directory to the Pi
python3 models/onnx/infer.py --demo   # self-test + latency benchmark
```

## AE Model Details

- Architecture: 15 → 7 → 3 → 7 → 15 (bottleneck dim=3)
- Trained on normal MetroPT-3 windows only (20,013 samples, no anomaly labels at train time)
- Threshold set at 98th percentile of normal-validation reconstruction error (2% FAR target)
- ROC-AUC = 0.978 on held-out labeled compressor failure windows

## Reproduce

```bash
# 1. Train AE (if not already done)
python3 demo/autoencoder.py --data ingest/out/metropt.csv --epochs 150

# 2. Export + verify parity
python3 demo/export_onnx.py

# 3. Run edge inference self-test
python3 models/onnx/infer.py --demo
```
