# THESEUS — End-of-Day-2 Snapshot
*Rollback anchor: tag `eod2` on branch `main`. This doc describes the system state as of the Day 2 (Jun 18) close.*

---

## What shipped today (Day 2)

### Mac Pi-node emulation
- Both UUV edge nodes (`uuv1-node` :54321, `uuv2-node` :54322) run as native arm64 containers on the Mac — Pis powered off, demo proceeds on the laptop.
- One Docker image (`analytics:latest`) serves both nodes; per-node config (`config.uuv1.yml` / `config.uuv2.yml`) is mounted via `RECEIVER_CONFIG`.
- `deploy/pi-emulation/up.sh --feed` starts both containers + a synthetic sensor stream. `down.sh` stops everything.
- Upstream MLflow Host-header fix landed in `deploy/mlflow/run.sh` (`MLFLOW_SERVER_ALLOWED_HOSTS` covering RFC-1918 + `host.docker.internal`) — required for the containers to pull models from the Mac host.

### Z-score detection fix (with metrics)
- Replaced `HalfSpaceTrees` (AUC ~0.65, near-zero normal/anomaly separation) with `RunningZScoreDetector` — online per-feature Welford mean/var; score = max |z| across sensor channels, squashed to [0,1).
- Trained on normal-only sensor data; streamed anomalies do not poison the baseline.
- Live scores: **normal ~0.2 / anomaly ~0.9** (clean separation on the live feed).
- Registered-model eval:

| Model | precision@k | F1 | false-alarm rate | ROC-AUC |
|-------|------------|-----|-----------------|---------|
| `uuv1_anomaly_deploy` | 0.96 | 0.96 | 0.013 | 0.9995 |
| `uuv2_anomaly_deploy` | 0.87 | 0.87 | 0.036 | 0.94 |

- Score is **explainable** (which sensor channel deviated, by how many σ) — T&E / accreditation asset.
- Models cloudpickled by value; edge container needs no custom class import.

### Destroyer STRIKE GROUP (Day-2 late round)
- **Three live destroyers on one laptop**: USS Theseus (DDG-118), USS Daedalus (DDG-119), USS Ariadne (DDG-120). Each runs its **own 6 subsystem containers** — **18 containers total** — on offset ports (DDG-118 `54541-54546`, DDG-119 `54551-54556`, DDG-120 `54561-54566`), each loading its own onboard model and scoring its own real data with a per-hull phase so they don't move in lockstep. (`deploy/ship-emulation/` + `gen_hull.py`; sister hulls regenerated on `up.sh --fleet`.)
- **9 models @production** in Node-3 MLflow (`:5050`), one per ship subsystem:

| Subsystem | Model | Dataset (real) | ROC-AUC |
|---|---|---|---|
| Machinery / Gas Turbine | `machinery_deploy` | naval CBM 316 | 1.00 |
| Propulsion / Engines | `propulsion_deploy` | turbofan C-MAPSS | 0.99 |
| Auxiliary / Air Plant | `auxiliary_deploy` | MetroPT compressor | 0.68* |
| Sonar / Water | `sonar_deploy` | UUV sensors | 0.9995 |
| C2 / Comms Link | `c2_deploy` | UUV command-link | 0.97 |
| Navigation | `nav_deploy` | UUV telemetry | 0.98 |
| UUV Own-Systems | `theseus-uuv` (autoencoder) | BlueROV2/ArduSub | 0.77 |
| Contacts / Tactical | `uuv2_anomaly_deploy` + AIS | UUV sonar / MarineCadastre | 0.94 |

  \* auxiliary is honestly noisier (real industrial compressor) — not hidden.
- **UI — new "Strike Group" scene** (`frontend/ui/src/components/strike/`): all subsystems lit live by severity, a deck.gl **tactical contacts map** (AIS + flagged spoof/jump/loiter/dark-gap), the **shore fleet brain**, animated **signed-delta sync** ship→shore, and the **provenance gate refusing a poisoned delta**. Believable fixture fallback; live now via `GET /api/destroyer`.
- **One-command launcher**: `deploy/strike_group_up.sh` (MLflow + models + 2 UUV nodes + all 3 destroyers live-fed + API) / `strike_group_down.sh`. Validated from a clean teardown → **18/18 containers, 19 live subsystems**. (Complements `deploy/demo_up.sh`, which repopulates the tamper-evident records + flywheel + preflight.)
- **DDIL "cut the cord" verified**: stop the MLflow registry → every container keeps scoring its last-good in-memory model.
- Still present from earlier today: BlueROV2 autoencoder import, the MLflow registry panel (`/api/mlflow` → `MlflowPanel`), the 2 Pi-emulation sonar/contacts nodes, the z-score detection fix above.

---

## Git commit at time of writing

```
9f4e7b9  theseus: destroyer strike-group — 8 subsystem models, ship containers, live API, UI   ← tag eod2
```

*The `eod2` tag marks the rollback anchor (commit `9f4e7b9`). Newer commits — the multi-hull strike group (3 live destroyers), the tactical contacts map, and the one-command launcher — advance `main` past it. Verify:*
```bash
git show -s --oneline eod2    # 9f4e7b9
git log --oneline -1          # current HEAD (advances past eod2 as the build continues)
```

---

## How to run the whole thing

**One command (the strike group):**
```bash
bash deploy/strike_group_up.sh            # MLflow + 9 models + 2 UUV nodes + 3 destroyers
                                          # (18 containers) live-fed + API on :8501
cd frontend/ui && npm run dev             # then open http://localhost:5173 → "STRIKE GROUP"
# Tear down:  bash deploy/strike_group_down.sh
```
`strike_group_up.sh --fast` skips model re-registration if they're already `@production`.

**Manual / piece-by-piece (fallback):**
```bash
# 1. Fleet brain
bash deploy/mlflow/run.sh && curl http://localhost:5050/health         # expect 200

# 2. Register models (py3.12 venv — cloudpickle cross-compat with the containers)
MLFLOW_TRACKING_URI=http://localhost:5050 deploy/mlflow/.venv312/bin/python models/subsystems/train_subsystems.py
MLFLOW_TRACKING_URI=http://localhost:5050 deploy/mlflow/.venv312/bin/python models/uuv/register_uuv_ae.py

# 3. Edge containers + feeds
bash deploy/pi-emulation/up.sh --feed                      # 2 UUV nodes (:54321/:54322)
bash deploy/ship-emulation/up.sh --fleet --feed --interval=2   # 3 destroyers (18 containers)

# 4. API + UI
python3 demo/api.py                                        # :8501
curl http://localhost:8501/api/destroyer                   # 3 hulls, subsystems live
cd frontend/ui && npm run dev                              # :5173

# 5. DDIL beat: stop MLflow -> containers keep scoring last-good
bash deploy/mlflow/run.sh stop
```

**The original records/flywheel demo** (separate from the container fleet) still runs via
`bash deploy/demo_up.sh` (repopulates the tamper-evident record + fleet flywheel + preflight).

---

## How to roll back

### Option A — check out the tag
```bash
git checkout eod2
# Repo is in the exact Day-2-close state. Read-only; detached HEAD.
# To return to main:
git checkout main
```

### Option B — reset main to eod2 (destructive — discards commits after eod2)
```bash
git reset --hard eod2
# Use only if post-eod2 commits broke something and you want to start clean.
# Inform the team before running this on a shared branch.
```

### Option C — new branch from eod2 (safest for debugging)
```bash
git checkout -b hotfix/from-eod2 eod2
# Work here; merge back to main when fixed.
```

### Verify rollback state
```bash
git show -s --oneline eod2          # 9f4e7b9 (the rollback anchor)
bash deploy/strike_group_up.sh      # MLflow + models + edge fleet + API come up
curl http://localhost:8501/api/destroyer | python3 -m json.tool | head   # hulls + subsystems live
```

---

## Known open items at EOD2 (not blocking Day 3)
- Branch reconciliation: Nick's `edge-mlflow-demo` uses a parallel `receiver/` dir vs the integrated `serve/receiver/` — needs a rebase before merge (Nick's lane).
- Juan's `remote-node-compose` is a stale fork off an older main — cherry-pick `k3s-remote-config.yaml` only.
- Pepr human-in-command rail: currently a presence check (any non-empty string), not a record-binding verify. Known; framed honestly in the demo.
- NV063 unscored volume: 1,699 open-universe alerts outside the n=50 curated eval are unmeasured. Frame as the Phase-I at-sea-labeling ask.
