# NV061 — Trajectory-Prediction Baseline (TrAISformer on `ct_dma`)

**Project:** THESEUS (maritime ship-brain) · **Companion bid:** NAVSEA **NV061** — *predictive movement for object-oriented tracking.*

This lane stands up the **"scoreboard to beat"** for vessel-trajectory prediction: the
published **TrAISformer** metric (arXiv:2109.03958) on the Danish Maritime Authority
`ct_dma` AIS dataset, plus a **real** train+eval run of that exact pipeline on **our**
hardware (Apple **MPS**), and a **constant-velocity floor** the learned model must beat.

State labels used throughout: `[published]` = copied from the paper · `[verified]` =
this code actually produced it on our box · `[pipeline-only]` = from a deliberately
short/reduced run, **not** the published full-training scoreboard.

---

## 1. The scoreboard to beat — `[published]`

Source: Duong Nguyen & Ronan Fablet, *"TrAISformer — A Transformer Network with Sparse
Augmented Data Representation and Cross Entropy Loss for AIS-based Vessel Trajectory
Prediction,"* **arXiv:2109.03958v4** (IEEE Access 2024, DOI 10.1109/ACCESS.2024.3349957),
**Table I**. Errors are **mean prediction error in nautical miles (nmi)**, evaluated on
the `ct_dma` ROI; lower is better; metric is the best-of-ensemble (min over 16 samples)
haversine error.

| Model | 1 h | 2 h | 3 h |
|---|---|---|---|
| LSTM_seq2seq | 5.83 | 8.39 | 11.64 |
| Conv_seq2seq | 4.23 | 6.77 | 9.66 |
| LSTM_seq2seq_att | 3.35 | 6.41 | 9.65 |
| Clustering_LSTM_seq2seq_att [18] | 0.78 | 1.93 | 3.66 |
| GeoTrackNet [45] (2nd best) | 0.72 | 1.59 | 2.67 |
| **TrAISformer (SOTA)** | **0.48** | **0.94** | **1.64** |
| TrAISformer_No-Stoch (ablation) | 1.28 | 2.88 | 5.02 |

Other published headline claims worth quoting in the bid:

- **Average prediction error below 10 nmi up to ~9–10 hours** (10 nmi ≈ clear-weather
  search-and-rescue visibility — the "still useful" threshold).
- **Max meaningful horizon: 9.67 h** for TrAISformer vs **1.67 h** for LSTM_seq2seq_att
  (~**5.8×** longer useful horizon than the deep-learning baselines).
- At 2 h, TrAISformer is the **only** model below 1 nmi (**41% better** than 2nd-best
  GeoTrackNet; **~2×** better than the clustering SOTA [18]).
- Discretization (mid-bin) approximation error at 0.01° resolution ≈ **0.15 nmi**
  (negligible vs the prediction error).

> **`to_beat` for NV061 = 0.48 / 0.94 / 1.64 nmi at 1/2/3 h** (and < 10 nmi to ~10 h).

The upstream code prints error in **km** (haversine, R = 6371 km); the paper reports
**nmi**. Conversion: **1 nmi = 1.852 km**. This runner reports both.

---

## 2. What actually executed on our box — `[verified]`

Hardware/runtime: **Apple MPS** (CUDA not available), `torch 2.10.0`, Python 3.14.4.
The upstream clone hardcodes `device=cuda:0` and `max_epochs=50`; `run_baseline.py`
inserts the clone on `sys.path` and overrides the `Config` at runtime (device → MPS,
epochs, data dir, batch size, ensemble samples). **No upstream file was edited.**

This was a **short pipeline-verification run** (`run_type: short-pipeline-verification`),
**not** the published scoreboard:

- 5 epochs · 2,000 train trajectories (of 9,144 usable) · 384 test trajectories ·
  ensemble n_samples = 8 (paper uses 16) · 57.4 M-param model · **~117 s end-to-end**.
- The pipeline **genuinely trains**: mean train loss **19.4 (untrained) → 14.4 → 9.0 →
  5.9 → 4.2 → 3.2** across the 5 epochs, then evaluates with the upstream sampling +
  haversine harness.

| 1/2/3 h | 1 h | 2 h | 3 h | notes |
|---|---|---|---|---|
| **`[published]` TrAISformer (50 ep)** | **0.48** | **0.94** | **1.64** | the target |
| `[verified][pipeline-only]` TrAISformer (5 ep, 2k traj) | **1.02** | **1.96** | **3.11** | nmi; this box, MPS |
| `[verified]` constant-velocity floor | 5.76 | 11.38 | 17.57 | nmi; same harness |

Reading of the result: after only **5 epochs on ~22% of the training set**, the pipeline
already lands in **GeoTrackNet/clustering-SOTA territory** (2nd–3rd place on the published
board) and **beats the constant-velocity floor by ~5.6×–5.8×** at every horizon. It is on
a clear trajectory toward the published 0.48/0.94/1.64 with full 50-epoch training on the
full set — i.e., the pipeline reproduces, end-to-end, on our hardware. The full per-step
curve (0–4 h, both km and nmi) is in `results/error_curve.csv`.

> Run-to-run, the learned numbers wobble ~±0.05 nmi from MPS floating-point
> nondeterminism in sampling; the CV floor is deterministic. The numbers above are from
> the artifacts currently in `results/` (`metrics.json`).

### Reproduce

```bash
cd /Users/force/Developer/Theseus/models/nv061

# short pipeline-verification run (the [verified] numbers above; ~2 min on MPS)
python3 run_baseline.py --epochs 5 --max-train 2000 --max-test 384 --n-samples 8

# fastest sanity check: dataset stats + 1 forward + 1 eval batch, no training
python3 run_baseline.py --smoke

# toward the published scoreboard (long; full set, 50 epochs, 16 samples)
python3 run_baseline.py --epochs 50 --max-train 100000 --max-test 100000 --n-samples 16
```

Outputs (written to `results/`): `metrics.json` (config + `[verified]`/`[published]`
numbers), `error_curve.csv` (per-step km+nmi for TrAISformer and CV), `run.log`.

Eval-harness fidelity notes: we replicate the upstream `trAISformer.py` evaluation
verbatim — ensemble **min** over samples, haversine in km, ROI constants
`v_ranges=[2,3,0,0]`, `v_roi_min=[lat_min,-7,0,0]` (the longitude offset is irrelevant to
the haversine distance — only longitude *differences* and the latitude-cosine terms
matter), and the upstream index convention where forecast index `i` maps to `i/6` hours,
so indices **6 / 12 / 18 = 1 / 2 / 3 h** (data is 10-min sampled, 6 steps/hour). Our
custom training loop matches the upstream forward/loss/optimizer but omits the upstream
`Trainer.train()` per-epoch plotting (it uses a Python-2 `iter(...).next()` call and a
removed `matplotlib` API that break on this stack); the model, loss, sampler and metric
are the upstream code unchanged.

---

## 3. NV061 framing

NAVSEA **NV061** asks for **predictive movement for object-oriented tracking** — given a
track's history, forecast where the object will be, with **defensible uncertainty**, far
enough ahead to be operationally useful (cue sensors, de-conflict, vector intercept).

The bid posture this baseline supports:

1. **Beat the constant-velocity / Kalman floor.** The classical track-prediction baseline
   is constant-velocity extrapolation (and its Kalman-filter cousin). On the *same* eval
   harness our CV floor is **5.76 / 11.38 / 17.57 nmi** at 1/2/3 h; the learned model is
   already **~5.6× better** at 2 h and the published TrAISformer is **~12× better**.
   "We beat the physics-only floor, with receipts" is the entry ticket.
2. **Multimodality at waypoints.** CV/Kalman cannot represent the branch at a waypoint
   (continue straight vs turn); the classification-over-grid + best-of-ensemble approach
   can, which is exactly why the published curve stays < 10 nmi out to ~10 h while the
   regression baselines blow past 10 nmi within ~2 h.
3. **Calibrated intervals, not just point error.** NV061's "predictive movement" needs an
   uncertainty *region*, not a single point. The ensemble sampler here is the seam to add
   **calibrated prediction intervals** (e.g., conformal coverage / per-horizon
   reliability) on top of the point metric — the natural NV061 differentiator beyond
   raw nmi.
4. **Human-in-command.** This is a forecasting/decision-support track: predictions cue
   operators; they are advisory, never an action of record.

---

## 4. Honest caveats

- The `[verified]` numbers are a **short pipeline-verification run** (5 epochs, ~22% of
  train, 8 samples, 384 test tracks, last-epoch weights — no best-val checkpointing, no
  HP tuning). They are **not** the scoreboard and must never be quoted as SOTA. The
  scoreboard is the `[published]` row only.
- **MPS nondeterminism** moves the learned numbers ~±0.05 nmi between runs; CV is exact.
- We reproduce the **published harness**, including its 10-min off-by-one in horizon
  labeling (index 6 reported as "1 h" ≈ physically 70 min). We keep the upstream
  convention so our numbers are directly comparable to Table I; see `error_curve.csv`
  (`pred_idx` is the raw 0-based step).
- `ct_dma` = Danish straits ROI (lat 55.5–58.0°N, lon 10.3–13.0°E), dense commercial AIS.
  It is the **published benchmark surface**, not NV061's operational data; transfer to a
  NAVSEA region/sensor mix is a separate step.
- Dataset (gitignored upstream clone): `../../data/datasets/traisformer/data/ct_dma/`
  (`*_train/valid/test.pkl`). Each row: `[lat, lon, sog, cog, unix_ts, mmsi]`, with
  lat/lon/sog/cog min-max normalized to `[0,1)`. Usable after filtering (moving-start +
  drop-NaN + len > 36): **9,144 train / 1,453 test** trajectories.
- License: the upstream TrAISformer code is **CeCILL-C** (`../../data/datasets/traisformer/LICENSE`).
