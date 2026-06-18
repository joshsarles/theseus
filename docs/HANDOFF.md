# THESEUS — Handoff: pull the datasets + train the Pi-deployable models

*Droid-to-Droid handoff. You are a fresh instance of me running on a teammate's machine. Goal:
pull the open datasets and train the edge (Raspberry Pi 5 / 4GB) models for THESEUS, continuing the
work already on `main`. This doc is self-contained for the critical path (setup → pull → train) and
points to the canonical docs for depth. Read it top to bottom once before touching anything.*

> **Honesty + license discipline is the whole game here.** Every number ships with its `n`, base
> rate, and caveats; every dataset is gated on commercial-use license; nothing non-commercial or
> license-unstated goes into a shipped/delivered artifact. Match that tone or you'll undo the work.

---

## 0. 60-second orientation

**THESEUS** = an airgapped, tamper-evident, **onboard maritime decision-support substrate**. Five
build beats: **SCREEN→CORRELATE** (AIS+ADS-B+radar into one picture), **DETECT** cold-start
Pattern-of-Life anomaly (no historical DB), **PREDICT** object trajectory (NV061), **SWAN-side**
machinery/HM&E health, **PROVE** (a hash-chained, tamper-evident record — the real moat). Target
SBIRs: **NV063** (maritime anomaly detection, the headline) and **NV061** (trajectory prediction).

The repo package is named `referee` (the Warhacker event scaffold; AGPL-3.0, stdlib-only by design);
the ML/data work (this handoff) lives in `ingest/`, `models/`, `eval/`, `train.py`, `serve/`.

**Strategic frame (read these — they're the "why"):**
- `docs/research/DECK_BLUE_OCEAN.md` — Applied Intuition's DECK opens the learning loop; THESEUS
  closes it onboard + makes it accreditable. "DECK feeds the loop; THESEUS closes it and proves it."
- `docs/vision/FLEET_LEARNING_VISION.md` — the 10/10 fleet-learning arc (learn local, sync safe).
- `docs/INTEGRATION_SPEC.md` — buy/borrow/build: compose best-of-breed (PyOD/River/Stone Soup/
  Sigstore/OSCAL/MLflow/ONNX), build only the differentiated onboard-DDIL + record + fleet-merge.
- `docs/WARHACKER_JUDGE_AUDIT.md` — the rubric + honest self-score.
- **The moat is the record + accreditation + a real ship feed, NOT the detectors/data (commodity).**
  The honest gaps: no open *real* naval HM&E telemetry, and the best anomaly labels (GFW) are
  non-commercial. Don't pretend otherwise.

---

## 1. Environment setup

```bash
# clone (standalone — this also auto-installs the IP-guard pre-commit hook via `make hooks`)
git clone https://github.com/joshsarles/theseus.git && cd theseus
git checkout main && git pull

# Python 3.14 (3.10+ works). Use a venv.
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -U pip

# Base deps. NOTE: requirements.txt is UTF-16 encoded — if pip chokes, re-encode first:
#   python3 -c "open('requirements.txt','w',encoding='utf-8').write(open('requirements.txt',encoding='utf-16').read())"
pip install -r requirements.txt

# ML EXTRAS NOT in requirements.txt but REQUIRED for training/export/bench (install these):
pip install h5py onnx onnxruntime skl2onnx pyod torch
#   h5py        -> N-CMAPSS HDF5 ingest
#   onnx/onnxruntime/skl2onnx -> ONNX export + Pi inference benchmark (the NV063 model)
#   pyod        -> eval/pyod_benchmark.py (anomaly-detector field)
#   torch       -> autoencoder models + PyOD AutoEncoder (CPU build is fine; large download)

make hooks      # install the IP-guard pre-commit hook (standalone clone only)
python3 -m pytest tests/ -q     # expect 21 passed
make smoke                       # expect SMOKE GREEN + verify PASS (the record chain)
```

Gotcha: on **macOS**, the bundled `unzip` cannot read >4GB Zip64 archives (bites N-CMAPSS — use the
Python recipe in §2). Linux `unzip` is fine.

---

## 2. Pull the datasets

Canonical source-of-truth for what to pull + licenses + sha256 = **`docs/research/datasets/DOWNLOADS.md`**
and the full catalog **`docs/research/datasets/DATASETS.md`**. Everything lands in `data/datasets/`
which is **gitignored** (never commit dataset bytes — license + size). Commands:

```bash
mkdir -p data/datasets && cd data/datasets

# --- the one NV063 needs first (MarineCadastre US AIS, public domain, ~277MB zip) ---
curl -L -o ais_us_2024_01_01.zip "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/AIS_2024_01_01.zip" \
  && unzip -o ais_us_2024_01_01.zip -d marinecadastre_us

# --- machinery (all commercial-clean) ---
curl -L -o cbm_naval_316.zip "https://archive.ics.uci.edu/static/public/316/condition+based+maintenance+of+naval+propulsion+plants.zip" \
  && unzip -o cbm_naval_316.zip -d cbm_naval_316
curl -L -o metropt3_791.zip "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip" \
  && unzip -o metropt3_791.zip -d metropt3
git clone --depth 1 https://github.com/edwardzjl/CMAPSSData cmapss

# --- AIS extras (CC BY 4.0 / CeCILL-C) ---
curl -L -o ushant_ais.zip "https://ndownloader.figshare.com/files/16442771" && unzip -o ushant_ais.zip -d ushant
git clone --depth 1 https://github.com/CIA-Oceanix/TrAISformer traisformer

# --- N-CMAPSS (US-Gov): 14.7GB archive with a NESTED data_set.zip; NASA mirror is throttled
#     (~1-3 MB/s, allow 1-2h). macOS unzip can't read it, so extract DS02 with Python: ---
mkdir -p ncmapss && curl -L --fail -o ncmapss/ncmapss_nasa.zip \
  "https://phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip"
python3 - <<'PY'
import zipfile, shutil, os
o = zipfile.ZipFile("ncmapss/ncmapss_nasa.zip")
inner = [n for n in o.namelist() if n.endswith("data_set.zip")][0]
with o.open(inner) as s, open("ncmapss/data_set.zip","wb") as d: shutil.copyfileobj(s, d, 1<<25)
z = zipfile.ZipFile("ncmapss/data_set.zip")
m = [n for n in z.namelist() if "DS02-006" in n and n.endswith(".h5")][0]
with z.open(m) as s, open("ncmapss/N-CMAPSS_DS02-006.h5","wb") as d: shutil.copyfileobj(s, d, 1<<25)
os.remove("ncmapss/data_set.zip")
print("extracted N-CMAPSS_DS02-006.h5")
PY
cd ..   # back to repo root
# sanity (compare against DOWNLOADS.md sha256 column): shasum -a 256 data/datasets/*.zip
```

Expected DS02 sha256: `47971a68b239ecb756833218a95d68ded6eb7e63ee84e86671c8b188de1ca765`.

**Never download** (license-blocked, see `DATASETS.md §2`): Global Fishing Watch (CC BY-NC — best
dark-vessel labels but non-commercial), Brest/Ray-2019 (NC), xView3-SAR (NC), OpenSky (research-only),
MIMII (copyleft). They're R&D/eval-only at most.

---

## 3. Normalize: the ingest adapters

Each adapter reads a local dataset and emits the **loop data contract** — a CSV of numeric feature
columns with the **LAST column = the target** — to `ingest/out/<name>.csv` (gitignored). See
`ingest/README.md`.

```bash
python3 ingest/cbm.py            # UCI #316 naval GT decay  -> target gt_compressor_decay (LOOP-LIVE)
python3 ingest/cmapss.py         # C-MAPSS FD001 RUL        -> target rul
python3 ingest/ncmapss.py --stride 100   # N-CMAPSS DS02 RUL (1Hz; stride subsamples) -> target rul
python3 ingest/metropt.py        # MetroPT-3 compressor     -> target is_anomaly (real failure windows)
python3 ingest/marinecadastre.py # AIS per-track features   -> target weak_anomaly_heuristic (WEAK, not GT)
python3 ingest/ushant.py         # AIS -> raw schema for demo/ais_pol.py (cross-region check)
```

---

## 4. Train the models

### 4a. NV063 AIS Pattern-of-Life anomaly — the most relevant, already built (extend it)
This is the first edge-deployable ML detector for the headline mission. **Already on `main`** at
`models/nv063/` — reproduce it, then extend (see §6 next steps).

```bash
python3 models/nv063/train_ais_anomaly.py   # full-pop IsolationForest, honest eval, ONNX(+int8) export
python3 models/nv063/pi_bench.py            # inference-only Pi-5-4GB footprint
```
**What it does + honest result (read `models/nv063/README.md`):** compact unsupervised IsolationForest
on the full 11,773-track MarineCadastre pool (curated-schema features; the analyst-curated n=50
excluded from the fit; `contamination=0.06` a-priori, NOT tuned on test). On the curated n=50 (9 pos):
- IForest: **P0.556 R0.556 F1 0.556 FAR 0.098 · ROC-AUC 0.802 PR-AUC 0.685**
- `ais_pol` rules baseline: P0.571 **R0.889** F1 0.696 FAR 0.146

Read it straight: the off-the-shelf ML matches precision with lower false-alarm, but **the domain
rules win recall** (the watch-relevant axis). ROC-AUC 0.80 = good separability → it's an
operating-point/recall gap. **Edge:** ONNX 1.25 MB, ONNX↔sklearn parity 1.000, ~1.2 ms/track single
thread, **74 MB inference RSS** — trivially fits a Pi 5 4GB. int8 gives no benefit for a tree
ensemble (documented). `model.pkl` is gitignored (reproducible); ship the `.onnx`.

### 4b. Machinery (SWAN-side health)
- **CBM (loop-live, the end-to-end demo):**
  ```bash
  python3 ingest/cbm.py
  python3 demo/stage_data.py --input ingest/out/cbm.csv   # seals data_staged into the record
  python3 demo/retrain.py                                  # trains GBR, registers theseus-cbm/vN, seals model_trained
  ```
  `demo/retrain.py` is **target-parametrized** (`--target`, or the `.target` sidecar = last column),
  so any adapter CSV trains through it: e.g. `python3 demo/stage_data.py --input ingest/out/ncmapss.csv && python3 demo/retrain.py --target rul`.
- **MetroPT autoencoder + benchmarks:** `python3 eval/benchmark.py`, `python3 eval/metropt_locv.py`.
- **N-CMAPSS RUL:** adapter is wired (`ingest/ncmapss.py`); **no model trained yet** — good next task
  (mirror the CBM/regression path or a small RUL regressor; export to ONNX like `models/nv063`).

### 4c. Trajectory (NV061) and streaming
- NV061 baseline: `models/nv061/` (TrAISformer `ct_dma` + CV/Kalman floor; see `eval/nv061`).
- A **River** online learner (Half Space Trees) was recently added (streaming anomaly — relevant to
  cold-start/DDIL). Grep `river` / check recent commits.

### 4d. Comparative anomaly field (needs pyod)
```bash
python3 eval/pyod_benchmark.py            # IForest/ECOD/COPOD/KNN/LOF/OCSVM/PCA/AutoEncoder vs ais_pol
```

### Edge/ONNX pattern (how Pi models are produced + measured)
`models/onnx/` holds the exported edge artifacts (`cbm_regressor*.onnx`, `autoencoder*.onnx`,
`ais_anomaly_iforest*.onnx`) + `infer.py`. For sklearn → ONNX use `skl2onnx.to_onnx(...,
target_opset={"": 17, "ai.onnx.ml": 3})` (the `ai.onnx.ml: 3` pin is REQUIRED for IsolationForest).
Benchmark single-thread (`intra_op_num_threads=1`) to mimic a Pi core; report model size, latency,
**inference-only** RSS (not the training-process RSS). `serve/` is the edge serving layer (currently a
regression contract in `serve/model_core.py` — an anomaly-serve path is still a TODO).

---

## 5. Eval + honesty harness (non-negotiable)
- `eval/score.py` — the scorer: `(track_id, is_anomaly)` preds vs labels → precision/recall/
  false-alarm/F1. `python3 eval/score.py --selftest` must pass.
- `eval/curated_labels.csv` (n=50) + `eval/curate_oparea.py` — the **honest, non-circular** NV063
  ground truth (analyst-curated; SME-pending). `eval/out/curated_metrics.json` = the canonical
  ais_pol number. `eval/RESULTS.md` = the honest write-up (read it).
- `eval/make_weak_labels.py` — weak PoL labels; **circular** with ais_pol, plumbing-only, NOT a skill
  metric. Never present weak-label agreement as detection performance.
- Hard rule: `n < 30` → label "illustration only". The n=50 set is a **pilot signal**, not production.

---

## 6. Current state + what's next (pick up here)
Done on `main`: all 6 adapters on real data; NV063 IForest edge model (§4a); CBM loop-live; machinery
benchmarks; N-CMAPSS pulled + wired; NV061 baseline. Suggested next, in priority order:
1. **Hybrid `ais_pol ∪ IForest` detector** — combine the rules' recall (0.89) with the ML's lower
   false-alarm; likely the best NV063 operating point. Quick, high-leverage.
2. **N-CMAPSS + MetroPT edge models** — train + ONNX-export + Pi-bench so every build beat has a
   benchmarked edge model (mirror `models/nv063/` exactly).
3. **Anomaly serve path** — extend `serve/` beyond the regression contract so anomaly models run in
   the sealed onboard loop (PROVE beat).
4. **Grow the curated NV063 set** past n=50 with NAVSEA SME sign-off → enables supervised learning +
   defensible precision/recall. Pursue a GFW commercial-use grant for real dark-vessel labels.

---

## 7. Conventions + guardrails (match these exactly)
- **HONESTY-FIRST:** every metric ships `n` + base rate + baselines (constant / kinematic / incumbent)
  + caveats verbatim. Never fabricate a number; if a dep/data is missing, say so and exit non-zero.
- **LICENSE-FIRST:** commercial-OK gates every dataset that touches a shipped/delivered artifact.
  `data/` is gitignored — never commit dataset bytes. NC/unstated = R&D/eval enclave only.
- **Scope rails:** SWAN-side machinery + AIS only (no out-of-domain). **Human-in-command, advisory-
  only.** Banned phrasing: "autonomous", "AI decides/acts", "self-controlled ship brain",
  "court-admissible" (without "by construction; not yet litigated"). The record is "tamper-evident",
  decisions are "recommended", sync is "human-authorized, eval-gated, provenance-attested".
- **Commits:** small, scoped, explicit `git add <paths>` (never `git add -A` — parallel agents work
  this repo; e.g. `fleet/` keys, `frontend/ui`, `ROADMAP.md`, `eval/RESULTS.md` change under you).
  Run `git status` first; never commit secrets. Co-author trailer:
  `Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>`.
  Don't push unless asked. The IP-guard pre-commit hook (`make hooks`) blocks retained-IP leakage.
- **Active files change under you:** `ROADMAP.md` and `eval/RESULTS.md` are edited by other agents —
  re-Read before editing. Treat untracked files as teammates' work; don't delete/clean them.

---

## 8. Gotchas (the ones that already bit)
- **macOS `unzip` fails on the 14.7GB N-CMAPSS Zip64** → use the Python recipe (§2). It also nests a
  `data_set.zip` inside the outer zip.
- **NASA PHM S3 mirror is throttled** (~1-3 MB/s) → N-CMAPSS takes 1-2h; background it.
- **`requirements.txt` is UTF-16** and **omits** h5py/onnx/onnxruntime/skl2onnx/pyod/torch → install
  them explicitly (§1).
- **skl2onnx IsolationForest** needs `target_opset={"": 17, "ai.onnx.ml": 3}` or conversion fails.
- **int8 dynamic quant ≠ smaller tree ensembles** (no MatMul weights) — expected; fp32 is already tiny.
- **`demo/out/` record churns** at demo time → `deploy/demo_up.sh` repopulates + restarts to GO.
- Report **inference-only** RSS for Pi claims, not the training-process peak.

---

## 9. The map (where things live)
```
ingest/         dataset -> loop-contract adapters (+ README, the contract)
models/nv063/   AIS anomaly edge model (train_ais_anomaly.py, pi_bench.py, README)  <- the new work
models/nv061/   trajectory baseline
models/onnx/    exported edge artifacts (.onnx) + infer.py
eval/           score.py + curated labels + RESULTS.md + pyod_benchmark.py (the honest harness)
demo/           the sealed loop: stage_data -> retrain -> record; ais_pol.py (rule detector); api.py
serve/          edge serving + DDIL model delivery (regression contract today)
train.py        IsolationForest fleet-anomaly demo (synthetic fleet JSON) + explainer
docs/research/datasets/  DATASETS.md (catalog) + DOWNLOADS.md (manifest) + A..F reports
docs/research/DECK_BLUE_OCEAN.md · docs/vision/FLEET_LEARNING_VISION.md · docs/INTEGRATION_SPEC.md
ROADMAP.md      living state (read first; edited by other agents)
```

Start by reproducing §4a, then take task #1 (hybrid detector) or #2 (N-CMAPSS/MetroPT edge models).
Keep it honest, keep it license-clean, keep the human in command.
