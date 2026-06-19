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

### Destroyer / strike-group build
- **Subsystem models registered** in Node-3 MLflow (`:5050`): `uuv1_anomaly_deploy@production` (MACHINERY / C2) + `uuv2_anomaly_deploy@production` (CONTACTS / sonar). Both alias-based (MLflow 3.x — stages removed).
- **Containers up**: `deploy/pi-emulation/up.sh` brings the two ship-node containers onto the `fleet` bridge network, each loading its model from `host.docker.internal:5050`.
- **API**: `demo/api.py` on `:8501` — `/api/state`, `/api/decision`, `/api/health`.
- **CIC dashboard**: `frontend/ui` on `:5173` — instrument-grade (amber-on-off-black, record-as-spine, deck.gl tactical). `POST /api/decision` seals ACCEPT/OVERRIDE into the tamper-evident chain live.
- **Full UUV dataset suite** committed to `serve/receiver/data/`: C2 link + sonar/water sensors + nav telemetry + combined, 25 labeled anomalies each (William).
- **DDIL fault-injection harness** (`serve/ddil_profiles.py`): 7 reproducible profiles (NOMINAL → DENIED). Last-good held 50/50 across all profiles.
- **BlueROV2/ArduSub autoencoder** (`models/uuv/`) imported: real UUV telemetry, ONNX-int8, Pi-bench verified. Registered as `theseus-uuv` in MLflow.
- **MLflow fleet-registry panel** in the CIC (`/api/mlflow` → `MlflowPanel` component) — shows registered models + aliases live.

---

## Git commit at time of writing

```
918b654  theseus: import theseus-uuv autoencoder (real BlueROV2/ArduSub telemetry, ONNX-int8, Pi-benched)
```

*This commit is tagged `eod2` at rollback time. Verify:*
```bash
git -C /path/to/theseus log --oneline -1   # should show 918b654
git tag eod2                                # if not already tagged
```

---

## How to run the whole thing

```bash
# 1. Fleet brain
bash deploy/mlflow/run.sh
curl http://localhost:5050/health          # expect 200

# 2. Register models (py3.12 venv — cloudpickle cross-compat with Pi containers)
MLFLOW_TRACKING_URI=http://localhost:5050 \
  deploy/mlflow/.venv312/bin/python serve/receiver/register_pickle_model.py

# 3. Ship containers + synthetic feed
bash deploy/pi-emulation/up.sh --feed
curl http://127.0.0.1:54321/health        # uuv1-node
curl http://127.0.0.1:54322/health        # uuv2-node

# 4. API
python3 demo/api.py --port 8501
curl http://localhost:8501/api/health     # expect {"connection":"live"}

# 5. CIC dashboard
cd frontend/ui && npm run dev
# Open http://localhost:5173

# 6. Tests
python3 -m pytest tests/ -q              # all green

# 7. DDIL beat (with internet off)
bash deploy/ddil_beat.sh                 # all PASS
```

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
git log --oneline -3         # should start at 918b654
bash deploy/mlflow/run.sh    # MLflow comes up
bash deploy/pi-emulation/up.sh --feed   # both nodes load models
curl http://127.0.0.1:54321/history | jq '.[-1].active_anomaly_score'   # ~0.2 normal
```

---

## Known open items at EOD2 (not blocking Day 3)
- Branch reconciliation: Nick's `edge-mlflow-demo` uses a parallel `receiver/` dir vs the integrated `serve/receiver/` — needs a rebase before merge (Nick's lane).
- Juan's `remote-node-compose` is a stale fork off an older main — cherry-pick `k3s-remote-config.yaml` only.
- Pepr human-in-command rail: currently a presence check (any non-empty string), not a record-binding verify. Known; framed honestly in the demo.
- NV063 unscored volume: 1,699 open-universe alerts outside the n=50 curated eval are unmeasured. Frame as the Phase-I at-sea-labeling ask.
