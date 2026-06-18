# `deploy/mlflow-sync/` — Shore → Ship MLflow registry delivery across a DDIL gap

Real, end-to-end staging of a trained model from a **connected shore enclave**
to a **disconnected ship** using the [`mlflow-export-import`](https://pypi.org/project/mlflow-export-import/)
tool — Juan's BDTS/CANES-style approach for a half-disconnected (DDIL) environment.

> **Juan's idea (implemented here, exactly):** "To mimic a real half-disconnected
> environment, output (with `mlflow-export-import`) the MLflow client outputs to
> file, then push those files to an MLflow server on another machine in a
> BDTS-CANES-like approach."

No mocks. Two real MLflow tracking servers stand in for two physical machines;
a real `GradientBoostingRegressor` (UCI #316 CBM data, the same recipe
`demo/retrain.py` trains) is registered on shore, exported to a file bundle,
carried across an air-gap **with the shore server stopped**, imported into the
ship, served from the ship, and the whole delivery is sealed into the Theseus
tamper-evident record.

---

## What this maps to (objective #4)

`README.md` objective #4: **"Stage model updates from shore without sneakernetting
(UDS/Zarf airgap bundle)."**

This directory is the **MLflow-registry layer** of that objective: it proves the
*model + its registry metadata* can cross a cross-domain boundary as a **file
bundle** (the removable-media / guard / data-diode stand-in) rather than a human
walking a USB stick around (sneakernet). The UDS/Zarf airgap bundle is the
transport vehicle; this is the MLflow registry payload that rides inside it.

- **SHORE** = connected enclave. Trains + registers the model.
- **SHIP** = disconnected platform (afloat). Cannot reach shore.
- **THE GAP** = `transfer/` — the file bundle that crosses the boundary. In
  production this is the signed UDS/Zarf bundle moved through the cross-domain
  solution; here it's a directory on disk.
- **BDTS/CANES framing**: the ship's network (CANES-analog) is denied/degraded;
  updates are batched to file and pushed across the boundary (BDTS-analog
  bulk-data transfer), not streamed over a live link.

---

## The real flow (8 steps, all verified)

```
SHORE (:5097, connected)                          SHIP (:5098, disconnected)
  │
  │ 1. mlflow server up (sqlite + file artifacts)        mlflow server up
  │ 2. train + register theseus-cbm vN  ──────────┐
  │ 3. load vN + predict  (source is real)         │
  │ 4. export-model -> file bundle ────────────────┼──► transfer/theseus-cbm-bundle/
  │      (mlflow-export-import + model artifacts)   │        ├─ model.json   (registry meta)
  │                                                 │        ├─ <run_id>/run.json (run meta)
  │ 5. ✂  SHORE STOPPED (cable cut)                 │        ├─ model_version_artifacts/vN/
  ✗  (shore /health now unreachable)               │        │     MLmodel, model.skops, …
                                                    │        └─ transfer_manifest.json
                                                    │
                                                    └──► 6. import bundle (SHORE DOWN)
                                                           7. pyfunc.load_model + predict
                                                           8. seal shore_to_ship_sync + verify
```

The model bytes that arrive on the ship are **byte-identical** to shore's
(`model.skops` is copied verbatim, not re-serialized), and shore vs ship
predictions match exactly — a faithful delivery, provable from the sealed record.

---

## Quick start (one command)

```bash
cd /Users/force/Developer/Theseus
deploy/mlflow-sync/.venv/bin/python deploy/mlflow-sync/run_sync.py --fresh
```

`--fresh` wipes `shore/ ship/ transfer/ out/record/` and runs the whole
delivery from scratch. Drop `--fresh` to run again and chain another sealed leaf
(idempotent: shore registers the next version, ship imports it, record grows).

Expected tail:

```
[PASS] 1. servers up (shore:5097 + ship:5098)
[PASS] 2. train + register on SHORE — theseus-cbm v1 rmse=0.003823
[PASS] 3. SHORE model loads + predicts — v1 predict[:3]=[0.989661, 0.969847, 0.99215]
[PASS] 4. export SHORE -> file bundle (mlflow-export-import + artifacts) — 11 files sha256=…
[PASS] 5. CUT THE CABLE: SHORE stopped (ship is now disconnected)
[PASS] 6. import bundle -> SHIP registry (with SHORE down) — theseus-cbm v1 on ship
[PASS] 7. SHIP serves the model (pyfunc.load_model + predict) — v1 predict[:3]=[0.989661, …]
[PASS] 8. seal shore_to_ship_sync + record verify_dir — PASS
OVERALL: PASS  (8/8 steps passed)
```

---

## Step-by-step (the exact commands the orchestrator runs)

All commands use this directory's own venv (`deploy/mlflow-sync/.venv`) and its
own ports/dirs, so they never touch Tommy's MLflow (:5001), the loop's
`demo/registry/`, or the repo-root default `mlflow.db`.

```bash
SYNC=/Users/force/Developer/Theseus/deploy/mlflow-sync
VPY=$SYNC/.venv/bin/python
SHORE=http://127.0.0.1:5097
SHIP=http://127.0.0.1:5098
BUNDLE=$SYNC/transfer/theseus-cbm-bundle

# 1. stand up both servers (two "machines")
bash $SYNC/servers.sh start shore
bash $SYNC/servers.sh start ship

# 2. train + register theseus-cbm on SHORE
MLFLOW_TRACKING_URI=$SHORE MLFLOW_RECORD_ENV_VARS_IN_MODEL_LOGGING=false \
  $VPY $SYNC/train_register_shore.py

# 3. prove the SHORE model loads + predicts
MLFLOW_TRACKING_URI=$SHORE \
  $VPY $SYNC/verify_side.py --side shore --uri $SHORE --version 1

# 4. THE GAP — export to a file bundle (Juan's "output to file" step)
MLFLOW_TRACKING_URI=$SHORE MLFLOW_RECORD_ENV_VARS_IN_MODEL_LOGGING=false \
  $VPY $SYNC/gap_export.py --model theseus-cbm --output-dir $BUNDLE

# 5. CUT THE CABLE — stop SHORE so the ship is provably disconnected
bash $SYNC/servers.sh stop shore

# 6. import the bundle into SHIP while SHORE is DOWN
MLFLOW_TRACKING_URI=$SHIP \
  $VPY $SYNC/gap_import.py --model theseus-cbm --bundle $BUNDLE \
  --experiment-name theseus-shore-to-ship

# 7. prove the SHIP serves the model
MLFLOW_TRACKING_URI=$SHIP \
  $VPY $SYNC/verify_side.py --side ship --uri $SHIP --version 1

# 8. seal the transfer into the record + verify offline
$VPY $SYNC/seal_transfer.py --model theseus-cbm --shore-version 1 --ship-version 1 \
  --bundle $BUNDLE --bundle-sha256 <hash-from-step-4> --record-dir $SYNC/out/record
```

You can also run the bare CLI the tool ships (what `gap_export.py` wraps):

```bash
MLFLOW_TRACKING_URI=$SHORE $SYNC/.venv/bin/export-model \
  --model theseus-cbm --output-dir $BUNDLE
```

…but see the compatibility note below — the raw CLI does not complete against
MLflow 3.14 without the shims `gap_export.py` / `gap_import.py` apply.

---

## Files

| File | Role |
|---|---|
| `config.sh` | shared paths/ports (shore :5097, ship :5098, transfer dir, record dir) |
| `servers.sh` | start/stop/status the two real MLflow servers (`start shore` / `stop shore` / `status`) |
| `train_register_shore.py` | trains the CBM model (reuses `demo/retrain.py` data + recipe) and registers `theseus-cbm` with a real MLflow sklearn flavor on shore |
| `gap_export.py` | **the gap**: `mlflow-export-import` registry+run metadata → file bundle, plus the model-version artifacts; emits a deterministic bundle SHA-256 |
| `gap_import.py` | imports the bundle into the ship (run lineage via `mlflow-export-import`; servable version registered verbatim from the bundled artifacts) |
| `verify_side.py` | loads `models:/theseus-cbm/<v>` from a given server and runs a real prediction (used for shore and ship) |
| `seal_transfer.py` | calls `demo/_record.seal(..., "shore_to_ship_sync", ...)` then offline-verifies the record |
| `run_sync.py` | the orchestrator: runs all 8 steps, prints PASS/FAIL each, `--fresh` to reset |
| `out/record/` | our own tamper-evident record (`chain.jsonl` + `bundle.json`) |
| `shore/ ship/ transfer/` | runtime state (gitignored, regenerated) |

---

## Environment + compatibility notes (real, honest)

This Mac runs **Python 3.14**, on which **MLflow 3.14's server does not boot**:
`ImportError: cannot import name 'Traversable' from 'importlib.abc'` (`Traversable`
moved to `importlib.resources.abc` in 3.14). So this directory uses a dedicated
**Python 3.13** venv (`/opt/homebrew/bin/python3.13 -m venv .venv`). The host's
system Python and other agents' setups are untouched.

`mlflow-export-import` 1.2.0 is the latest on PyPI and predates two MLflow 3.x
changes; both are handled here without editing the package:

1. **`tabulate` missing** from its declared deps → installed into the venv.
2. **Non-JSON-serializable `ModelVersionDeploymentJobState`** (a field MLflow
   3.14 added to model versions) breaks the exporter's `json.dumps`. Fixed at
   runtime by wrapping `io_utils.json.dumps` with `default=str`
   (`gap_export.py` / `gap_import.py`). This only makes metadata serialization
   tolerant; the transferred model artifacts are unaffected.
3. **MLflow 3.x logged-model store**: `mlflow.sklearn.log_model()` now writes to
   the *logged-model* store, not the run's artifact dir, and sets the registered
   version's `source` to `models:/m-<id>`. Consequences:
   - `mlflow-export-import`'s run-artifact export captures **empty** model
     artifacts → `gap_export.py` additionally pulls each version's real
     artifacts via the supported `mlflow.artifacts.download_artifacts(...)`.
   - `mlflow-export-import`'s `ModelImporter` **cannot** import a 3.x version
     (it raises `Cannot find run ID … in source field 'models:/…'` because it
     expects the 2.x `runs:/…` convention) → `gap_import.py` uses the tool's
     `RunImporter` for run lineage and registers the **servable** version from
     the bundled artifacts directly.
4. **skops re-serialization**: loading the sklearn model and re-logging it after
   `RunImporter` runs in the same process yields a corrupt 354-byte artifact
   (skops trusted-type state interaction). `gap_import.py` therefore copies the
   `model.skops` + `MLmodel` **verbatim** and registers from the run URI — which
   is also the correct air-gap behavior (the exact shore bytes arrive on ship).

### Reproduce the environment from scratch

```bash
/opt/homebrew/bin/python3.13 -m venv deploy/mlflow-sync/.venv
deploy/mlflow-sync/.venv/bin/python -m pip install \
  "mlflow==3.14.0" "scikit-learn==1.8.0" mlflow-export-import tabulate
```

---

## What's real vs pending

**Real (runs on this Mac, verified):**
- Two live MLflow tracking servers (sqlite + file artifact store), shore :5097 /
  ship :5098, distinct from Tommy's :5001 and the loop's state.
- Real CBM model trained on UCI #316 and registered on shore.
- Real `mlflow-export-import` export to a file bundle (+ deterministic SHA-256).
- Real import into the ship **with shore stopped** (disconnection proven via
  shore `/health` being unreachable at import time).
- Ship serves the model: `pyfunc.load_model` + prediction, identical to shore.
- Delivery sealed as `shore_to_ship_sync` leaves; `verify_dir` PASS.

**Pending / not done here (out of scope, owned elsewhere):**
- Wrapping this bundle inside the actual **UDS/Zarf** signed airgap package and
  pushing through a real cross-domain solution (lives under `deploy/uds/`, owned
  by another agent — not touched).
- Cosign signature on the transfer bundle (the record SHA-256 is the integrity
  tag today; production swaps to the Ed25519-signed ledger per `referee/chain.py`).
- Multi-version stage/promote policy on the ship (today every shore version is
  imported and registered in order).
```
