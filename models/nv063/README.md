# NV063 — deployable AIS Pattern-of-Life anomaly model (Pi 5 / 4GB)

The headline maritime-anomaly mission shipped as the rule-based `demo/ais_pol.py`. This is the
first **trained, edge-deployable ML detector** for the same beat: a compact, explainable,
**unsupervised IsolationForest** trained on the full MarineCadastre track population, exported
to ONNX, and benchmarked to run on a Raspberry Pi 5 (4GB).

## What it is
- **Data:** MarineCadastre US AIS 2024-01-01 (public domain). 1.5M raw rows → **11,773 eligible
  tracks** (≥6 fixes) — the exact eligible pool from `eval/RESULTS.md`.
- **Features (per track, curated schema):** `n_fixes, dur_h, sog_min, sog_mean, sog_max,
  still_frac, max_gap_min, max_jump_kn, vessel_type` — re-extracted with the **identical
  definitions** used by `eval/curate_oparea.py`, so the analyst-curated n=50 are a labeled subset
  of the training pool with no schema drift.
- **Model:** `Pipeline(StandardScaler, IsolationForest(n_estimators=200, contamination=0.06))`.
  Contamination = the a-priori population estimate from `eval/RESULTS.md` (~5–6%), **not tuned on
  the test labels**. The 50 curated tracks are **excluded from the fit** (no train-on-test).
- **Unsupervised:** labels are used only for evaluation. Metric definitions match `eval/score.py`.

## Honest results (curated n=50; 9 pos / 41 neg)
| detector | precision | recall | F1 | false-alarm | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|---|
| **IsolationForest (this model)** | 0.556 | 0.556 | 0.556 | **0.098** | **0.802** | **0.685** |
| `ais_pol` rules (baseline) | **0.692** | **1.00** | **0.818** | **0.098** | — | — |

**Read it straight:** on this curated set the **domain rules (`ais_pol`) now dominate** the
off-the-shelf unsupervised model on every operating-point metric — precision (0.69 vs 0.56),
recall (1.0 vs 0.56), F1 (0.82 vs 0.56) — at the **same** false-alarm rate (0.098). IsolationForest's
value is its **threshold-free ranking** (ROC-AUC 0.80 / PR-AUC 0.69) and as an **ensemble member**,
not as a standalone replacement. Pool-wide IForest flags **713/11,773 (6.1%)** vs `ais_pol`'s 8.6%.
*(`ais_pol` numbers reproducible: `eval/score.py` against committed `eval/out/ais_pol_preds.csv`.)*

**So what:** this is the honest ML baseline NV063 needs — it (a) sets the "what does a generic
detector get" bar, (b) confirms the bespoke rules' recall edge, and (c) motivates the real next
step (a **hybrid rules ∪ ML** detector, and supervised learning as the analyst-curated set grows
past n=50 with NAVSEA SME sign-off). **Caveats (loud):** n=50 is a pilot signal, wide CIs,
SME-pending — same discipline as `eval/RESULTS.md §2`.

## Edge / Pi 5 (4GB) — it runs onboard
- **Model size:** `models/onnx/ais_anomaly_iforest.onnx` = **1.25 MB** (fp32).
- **ONNX↔sklearn label parity:** **1.000** (the exported model is the trained model).
- **Latency (onnxruntime, 1 thread):** **~1.2 ms/track** single, **0.03 ms/track** batched-64.
- **Inference-only RSS:** **74 MB** (numpy + onnxruntime) — vast headroom under 4 GB
  (`pi_bench.json`).
- **int8:** dynamic quantization gives no benefit here (a TreeEnsemble stores float thresholds, so
  there are no MatMul/Gemm weights to quantize); the fp32 artifact is already tiny. Documented, not
  shipped as the primary.

## Reproduce
```bash
# requires the gitignored MarineCadastre AIS on disk (see docs/research/datasets/DOWNLOADS.md)
python3 models/nv063/train_ais_anomaly.py      # extract → fit → eval → ONNX(+int8) → results.json
python3 models/nv063/pi_bench.py               # inference-only Pi-5-4GB footprint → pi_bench.json
```

## Files
- `train_ais_anomaly.py` — extract + fit + honest eval + ONNX export + bench (the recipe).
- `pi_bench.py` — inference-only Pi footprint measurement.
- `meta.json` — model params + features + sha256 (sealable into the record).
- `results.json` — full eval + edge benchmark.
- `pi_bench.json` — the honest Pi inference numbers.
- `model.pkl` — sklearn pickle (gitignored; reproducible). `models/onnx/ais_anomaly_iforest*.onnx` — edge artifacts.
