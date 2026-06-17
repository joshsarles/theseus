# THESEUS — model benchmarks (the machinery organ, with receipts)

*Reproducible benchmarks from the local data, Jun 17 2026. `python3 models/benchmark.py` (CBM/C-MAPSS/MetroPT-random) + `python3 models/metropt_locv.py` (the honest MetroPT protocol). Independent reproductions from `ingest/out/*.csv` + raw data — Tommy's MLflow/loop runs live on his server; CBM cross-checks the loop registry. Honest baselines + leakage-free protocols so each number means something.*

## What the machinery organ proves
One model-delivery spine ingests **three datasets** spanning **naval simulated GT → aero GT transfer → real operational compressor**, in both **regression** and **classification** — the SWAN-side "detect impending failure before the watch" organ is **dataset-agnostic**.

| Dataset | What it is | Task | Metric | **Result** | Baseline | Protocol |
|---|---|---|---|---|---|---|
| **UCI #316 CBM** | real frigate gas-turbine decay (CC BY 4.0) — the bullseye | regress `gt_compressor_decay` | RMSE | **0.00382** | 0.0147 (mean) | random 80/20 |
| **NASA C-MAPSS FD001** | turbofan run-to-failure (US-Gov) — GT-RUL transfer | regress RUL (cycles) | RMSE | **50.88 cyc** | 78.93 (mean) | unit-split (1-80 / 81-100) |
| **MetroPT-3** | real air-compressor, 4 reported air-leak failures (CC BY 4.0) | classify `is_anomaly` | F1 | **0.26 (honest LOFO)** · 0.94 random-split was **LEAKY** | base rate 1.95% | leave-one-failure-out CV |
| **MetroPT-3 (autoencoder)** | same, unsupervised | reconstruction-error anomaly | ROC-AUC | **0.978** (built by the team) | — | train-on-normal |

## Per-dataset read (honest)
- **UCI #316 CBM — the headline.** RMSE **0.00382**, **3.8× better than predict-the-mean (0.0147)**, on a *real naval gas-turbine* decay coefficient; cross-checks the loop registry (0.003823). Strongest, cleanest, most on-target result.
- **C-MAPSS FD001 — transfer proof, uncalibrated.** RMSE **50.88 cyc** vs 78.93 mean on a proper **unit-split** (no engine leaks across train/test) — the organ extracts degradation signal on turbofan GTs. **CAVEAT:** raw RUL, no piecewise cap, internal split of the train file; the official protocol (RUL cap ~125 + held-out test set) yields far lower RMSE (published SOTA ≈ 12–16). 50.88 is an honest **transfer floor**, not a leaderboard number.
- **MetroPT-3 — the honest number is much lower than it first looked.** The original **random 80/20 split gave F1 0.94 — but that LEAKS**: 10-min windows are temporally autocorrelated, so near-identical adjacent windows of the *same* failure land in both train and test. Under **leave-one-failure-out CV** (`models/metropt_locv.py`: 4 folds over nearest-failure temporal segments, so the test failure's windows are never in training) the supervised classifier collapses to **precision 0.36 / recall 0.21 / F1 0.263 / FAR 0.0072** (micro-averaged, 25,515 windows). Per-fold it swings wildly (recall 0.97 on one held-out failure, 0.0 on another) — **each air-leak manifests differently, so a supervised model barely generalizes to an unseen failure.** This is the real result, and it's the case *for* unsupervised detection.

## The recommended detector is the autoencoder — and it's now built `[BUILT by the team]`
Because supervised LOFO generalizes poorly (above) and most shipboard telemetry is **unlabeled**, the right model is an **unsupervised autoencoder** (train on normal, threshold on reconstruction error — no failure labels needed). The team built it: **ROC-AUC 0.978 on the real MetroPT air-leak failures** (`demo/`, Tommy's direction). That is the headline machinery-anomaly number to carry forward; the supervised LOFO 0.26 is the honest *supervised floor* that motivates it.

## Honest gaps
1. **No open in-situ naval HM&E telemetry exists** (proprietary). Naval relevance = **transfer**: UCI #316 (sim-naval GT) anchor + C-MAPSS (aero GT) + MetroPT (real compressor). Stated plainly; only UCI #316 is naval (and it's simulator-generated).
2. **C-MAPSS** number is an uncapped internal-split floor; re-run under the official protocol if RUL becomes a bid line.
3. **MetroPT** supervised result is honest now (LOFO); the autoencoder AUC is the number to feature, with a by-failure eval to match the LOFO rigor.

## Cross-references
- Adapters: `ingest/` (`cbm.py`, `cmapss.py`, `metropt.py`). Raw data + licenses: `docs/research/datasets/DOWNLOADS.md`.
- Benchmark scripts: `models/benchmark.py`, `models/metropt_locv.py` (results JSONs alongside). Loop: `demo/README.md`. Autoencoder: `demo/` (team). AIS anomaly eval: `eval/RESULTS.md`.
