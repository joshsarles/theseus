# THESEUS — model benchmarks (the machinery organ, with receipts)

*Reproducible benchmarks from the local data, Jun 17 2026. Run `python3 models/benchmark.py` (sklearn only; writes `models/benchmark_results.json`). These are **independent reproductions** from `ingest/out/*.csv` + raw C-MAPSS — Tommy's MLflow/loop runs live on his server (not reachable from this shell); CBM cross-checks the loop registry. Honest baselines included so each number means something.*

## What the machinery organ proves
One model-delivery spine ingests **three datasets** spanning **naval simulated GT → aero GT transfer → real operational compressor**, in both **regression** and **classification** — i.e. the SWAN-side "detect impending failure before the watch" organ is **dataset-agnostic**, not a one-dataset trick.

| Dataset | What it is | Task | Metric | **Result** | Baseline | Split |
|---|---|---|---|---|---|---|
| **UCI #316 CBM** | real frigate gas-turbine decay (CC BY 4.0) — the bullseye | regress `gt_compressor_decay` | RMSE | **0.00382** | 0.0147 (predict-mean) | random 80/20 |
| **NASA C-MAPSS FD001** | turbofan run-to-failure (US-Gov) — GT-RUL transfer | regress RUL (cycles) | RMSE | **50.88 cyc** | 78.93 (predict-mean) | unit-split (1-80 / 81-100) |
| **MetroPT-3** | real air-compressor w/ 4 reported air-leak failures (CC BY 4.0) | classify `is_anomaly` | F1 | **0.94** (P 0.931 / R 0.949) | base rate 1.95% | see caveat ⚠ |

## Per-dataset read (honest)
- **UCI #316 CBM — the headline.** RMSE **0.00382**, **3.8× better than the predict-the-mean baseline (0.0147)**, on a *real naval gas-turbine* decay coefficient. Cross-checks the loop's own registry (`demo/registry/theseus-cbm` RMSE 0.003823) — the `ingest/cbm.py` adapter output is loop-equivalent. This is the strongest, cleanest result and it's on the most on-target data we have.
- **C-MAPSS FD001 — transfer proof, uncalibrated.** RMSE **50.88 cycles** vs 78.93 mean-baseline on a proper **unit-split** (no engine leaks across train/test) — the organ extracts real degradation signal on turbofan GTs. **CAVEAT (loud):** this is raw RUL with **no piecewise cap** and an internal split of the train file; the **official C-MAPSS protocol** (RUL capped at ~125, the held-out test set + RUL truth) yields far lower RMSE (published SOTA ≈ 12–16). 50.88 is an honest **floor** that proves transfer, **not** a leaderboard number. The point is generalization across GT platforms, not beating the FD001 SOTA.
- **MetroPT-3 — real-failure anomaly, leakage-inflated.** P **0.931** / R **0.949** / F1 **0.94**, false-alarm rate 0.0014, on real company-reported air-leak windows (2% base rate). **CAVEAT (loud):** the time-ordered split left one class empty (failures cluster in time), so it **fell back to a random 80/20 split** — and 10-min windows are temporally autocorrelated, so a random split **leaks** and **overstates** these numbers. The honest evaluation is **leave-one-failure-out CV** or a strict time-split that preserves at least one failure per fold; expect lower real numbers. Treat F1 0.94 as an **optimistic upper bound**, not a claim.

## Honest gaps + the recommended next model
1. **No real in-situ naval HM&E telemetry exists openly** (proprietary). The naval-relevance story is **transfer**: UCI #316 (sim-naval GT) is the anchor; C-MAPSS (aero GT) + MetroPT (real compressor) prove the organ generalizes. Stated plainly in any proposal — nothing here is real shipboard data except UCI #316's simulator-generated frigate plant.
2. **MetroPT eval needs a leakage-free protocol** (leave-one-failure-out CV). That is the single most important fix to make the anomaly number defensible.
3. **The right unsupervised model is an autoencoder** (Tommy's direction — confirmed). Most shipboard telemetry will be **unlabeled**; a reconstruction-error autoencoder (train on normal, threshold on reconstruction error) fits cold-start anomaly far better than a supervised classifier that needs failure labels. Recommend: AE on MetroPT (eval by-failure) + on CBM residuals, reported with the same precision/recall/false-alarm-rate harness as `eval/score.py`.
4. **C-MAPSS**: re-run under the official protocol (RUL cap 125 + official test set) for a comparable number, if RUL prediction becomes an NV061-adjacent bid line.

## Cross-references
- Adapters that produced the CSVs: `ingest/` (`cbm.py`, `cmapss.py`, `metropt.py`). Raw data + licenses: `docs/research/datasets/DOWNLOADS.md`.
- The delivery loop these models register into: `demo/README.md` (Stage → Retrain → Update, every step sealed). MLflow tracking is Tommy's server (`MLFLOW_TRACKING_URI` when configured).
- Anomaly scorer + the NV063 AIS results: `eval/score.py`, `eval/RESULTS.md`.
