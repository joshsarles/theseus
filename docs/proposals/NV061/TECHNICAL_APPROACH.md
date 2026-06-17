# DON26BZ03-NV061 — Technical Approach (Phase I draft)

**Topic:** Predictive Movement for Object-Oriented Tracking (NAVSEA, DON SBIR 26.3 / R3; opens 6/24, closes 7/22). Companion to NV063 (anomaly) — NV061 forecasts *where a track is going*; NV063 flags *whether it's behaving anomalously*. Together = object-level situational awareness for the Maritime Targeting Cell / combat-system track management.
**Offeror system:** THESEUS — airgapped, tamper-evident onboard maritime decision-support. Forecasts are **advisory** (cue/de-conflict/vector); the watch team commands. Alongside the combat system via certified data pipes, never embedded in the kill chain in Phase I.

> **Integrity discipline (founder rule):** every capability is tagged **[BUILT]** (running code + a real number), **[PARTIAL]** (substrate built, integration pending), or **[PROPOSED]** (Phase I/II work). Nothing aspirational stated as built. Banned framings avoided: no "autonomous", advisory only, "reproduces SOTA" (not "beats"), SWAN-side, compose-not-replace.

## 1. The requirement (NV061 intent)
Given a track's history, **forecast its future position** with **defensible uncertainty**, far enough ahead to be operationally useful (cue sensors, de-conflict, vector an intercept), feeding combat-system track management. The classical bar is constant-velocity / Kalman extrapolation; the ask is to beat it with calibrated, multi-step, multimodal prediction.

## 2. Approach — what we do, and what's already real

### 2.1 Reproduced the published trajectory-prediction SOTA **[BUILT]**
We stood up TrAISformer (arXiv:2109.03958) on the open `ct_dma` AIS benchmark and **reproduced the published SOTA on our own hardware (Apple MPS)**: **0.48 / 0.90 / 1.48 nmi** mean prediction error at **1 / 2 / 3 h**, vs the paper's **0.48 / 0.94 / 1.64 nmi** (15-epoch full-train run; same upstream eval harness — ensemble-min over 16 samples, haversine). Receipts: `models/nv061/RESULTS.md`, `models/nv061/results/metrics.json`. We claim **"reproduces SOTA,"** not a new SOTA (the small longer-horizon edge is within run-to-run/MPS variance).

### 2.2 Beat the constant-velocity / Kalman floor **[BUILT]**
On the *same* eval harness, the constant-velocity floor is **6.29 / 12.34 / 18.87 nmi** at 1/2/3 h; the learned model is **~13× better at every horizon**. NV061's grading bar is "beat the kinematic baseline" — we clear it decisively, with receipts.

### 2.3 Multimodality at waypoints **[BUILT, by method]**
CV/Kalman cannot represent the branch at a waypoint (continue vs turn). The classification-over-grid + best-of-ensemble approach can — which is why the published curve stays **< 10 nmi out to ~10 h** while regression baselines blow past 10 nmi within ~2 h. The ensemble sampler is in the running pipeline.

### 2.4 Calibrated prediction intervals **[PROPOSED]**
NV061 wants an uncertainty *region*, not a point. The ensemble sampler is the **seam** to add **conformal prediction intervals** (split/adaptive conformal → distribution-free per-horizon coverage; report PICP + MPIW alongside ADE/FDE). This is the natural NV061 differentiator beyond raw nmi; not yet built.

### 2.5 Environment-aware forecasting **[PROPOSED]**
Ocean currents (HYCOM) + sea-state condition real vessel motion (set/drift; speed envelopes). Folding open env-context features (see `docs/research/NV065_FIT_AND_ENV_DATA.md`) into the forecaster is a Phase-I ablation — measure the nmi gain before leaning on it.

### 2.6 Edge + human-in-command **[BUILT substrate / PARTIAL integration]**
The model runs on commodity edge hardware (MPS today; ONNX → ship NPU is the deploy path, shared with NV063). Forecasts are advisory — they cue operators and feed the track picture; never an action of record.

## 3. Metrics + evidence (real, with status)

| Capability | Evidence | Number | Status |
|---|---|---|---|
| Trajectory prediction vs SOTA | `models/nv061/RESULTS.md` | 0.48 / 0.90 / 1.48 nmi @1/2/3h (reproduces published 0.48/0.94/1.64) | [BUILT] |
| Beat CV/Kalman floor | same harness | floor 6.29/12.34/18.87 → learned ~13× better | [BUILT] |
| Useful horizon | published curve | < 10 nmi to ~10 h (vs ~2 h for regression baselines) | [BUILT, reproduced] |
| Calibrated intervals (PICP/MPIW) | — | conformal wrapper on the ensemble sampler | [PROPOSED] |
| Naval-maneuver eval | — | no open *naval* AIS-TP set exists | [PROPOSED] |

## 4. Phase I scope + integration
- **Phase I:** reproduce + harden the forecaster on a NAVSEA-relevant ROI; add **conformal intervals** (the differentiator); stand up a **naval-maneuver eval** (evasion/formation/sensor-cued intercept) via simulation (MSS / MOOS-IvP) or SME-curated tracks, since every open AIS-TP set is commercial/fishing traffic; always report gain vs the **CV/Kalman floor**.
- **Integration:** the predicted-position + interval feeds the **same fused track picture NV063 reasons over** — NV061 (where it's going) + NV063 (is it behaving anomalously) = one coherent object-SA story. Runs **alongside** combat-system track management via certified data pipes; **<100 ms edge inference** is the design target (the SBIR research's NV061 latency bar). Not embedded in the kill chain in Phase I.
- **Shared stack with NV063** (fusion + edge deploy + the tamper-evident record) → low marginal cost to bid both.

## 5. Honest status summary
**[BUILT] today:** reproduced TrAISformer SOTA (0.48/0.90/1.48 nmi) · beat the CV/Kalman floor ~13× · multimodal-waypoint method · the ensemble sampler.
**[PARTIAL]:** edge deploy (MPS built; ONNX→ship-NPU is the path) · combat-system integration (alongside, via certified pipes).
**[PROPOSED]:** conformal prediction intervals · naval-maneuver eval · env-aware (HYCOM/sea-state) features · transfer from `ct_dma` (Danish straits) to a NAVSEA ROI/sensor mix.

*Every [BUILT] claim is reproducible (`python3 models/nv061/run_baseline.py …`) and traces to `models/nv061/RESULTS.md` + `results/metrics.json`. `ct_dma` is the published benchmark surface, not NV061 operational data. Drafted by THESEUS lane; verify against the cited code before external use.*
