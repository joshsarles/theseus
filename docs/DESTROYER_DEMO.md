# THESEUS — Strike Group Demo Script
*Presenter-facing. 5–7 beats, ~5 minutes. Everything here runs on the Mac (Node 3) — no Pis required. Rehearse the full sequence once before judges arrive.*

---

## The narrative

**A destroyer is a self-contained city.** Machinery keeps the lights on. Propulsion drives the shaft. Navigation holds the track. Sonar hunts below the surface. C2 holds the link. The auxiliaries balance the grid. Own-systems watches the hull and UUV. Contacts tracks what's out there. Each of these is a distinct system, on a distinct bus, run by a distinct crew.

Theseus mirrors that architecture: **each subsystem runs its own onboard ML model in its own container**, isolated, low-RAM, inference-only at the edge. A human watch officer is always in command — the system recommends, the officer decides, and every decision is sealed in a tamper-evident record.

When the ship is **not in a contested environment**, it syncs **model deltas — never raw sensor data** — to the fleet brain ashore (Node 3 MLflow in the demo). The fleet brain merges only the **provenance-attested** updates. A captured node can't poison the fleet: its delta is rejected at the gate because it lacks the signed attestation chain. A frozen model can't hide: every update is eval-gated before it promotes. The result is a fleet that keeps learning at sea — **Tesla-fleet-style, but human-authorized, eval-gated, and provenance-attested**. That sealed record is not a side feature: it is what makes fleet learning **accreditable** — a cATO-for-AI path, in the AO's own OSCAL language.

The demo runs **three live destroyers** — USS Theseus (DDG-118), USS Daedalus (DDG-119), USS Ariadne (DDG-120) — each with 8 subsystem containers (18 containers total across the strike group), all streaming simultaneously with per-hull phase offsets so they don't move in lockstep.

---

## The 8-subsystem table

*Each hull runs all 8 subsystems. The same image, the same registered models — just different host ports per hull.*

| # | Subsystem | Dataset / source | Model / detector | AUC | Detector type |
|---|-----------|-----------------|-----------------|-----|---------------|
| 1 | **MACHINERY / HM&E** | Naval gas-turbine CBM (UCI #316 real compressor data) | `machinery_deploy` | 1.00 | RunningZScoreDetector (max-σ) |
| 2 | **PROPULSION** | Turbofan degradation C-MAPSS | `propulsion_deploy` | 0.99 | RunningZScoreDetector (max-σ) |
| 3 | **AUXILIARY** | MetroPT compressor dataset | `auxiliary_deploy` | 0.68 | RunningZScoreDetector (max-σ) |
| 4 | **SONAR** | UUV sonar / water-sensor data (pressure, temp, salinity anomalies) | `sonar_deploy` | 0.9995 | RunningZScoreDetector (max-σ) |
| 5 | **C2 LINK / COMMS** | Real UUV C2 telemetry (failed-integrity flags, 20s latency spikes, ABORT_MISSION events) | `c2_deploy` | 0.97 | RunningZScoreDetector (max-σ) |
| 6 | **NAVIGATION / IMU** | UUV nav telemetry (latency + seq-gap features) | `nav_deploy` | 0.98 | RunningZScoreDetector (max-σ) |
| 7 | **OWN SYSTEMS (UUV)** | BlueROV2/ArduSub telemetry — real UUV, ONNX-int8, Pi-bench verified | `theseus-uuv` (Conv1d autoencoder) | 0.77 | Conv1d autoencoder |
| 8 | **CONTACTS / AIS** | MarineCadastre AIS (real vessel tracks, Gulf + Ushant cross-validation) | `uuv2_anomaly_deploy` | 0.94 | RunningZScoreDetector (max-σ) + cold-start PoL |

All 9 models (`machinery_deploy`, `propulsion_deploy`, `auxiliary_deploy`, `sonar_deploy`, `c2_deploy`, `nav_deploy`, `uuv1_anomaly_deploy`, `uuv2_anomaly_deploy`, `theseus-uuv`) are registered `@production` in the Node-3 MLflow on `:5050`.

The flagship (DDG-118) also hosts the two UUV Pi-emulation nodes on `:54321` (own-systems) and `:54322` (contacts/AIS).

---

## Port map — three live hulls, 18 containers

| Hull | Subsystem | Host port |
|------|-----------|-----------|
| DDG-118 USS Theseus | MACHINERY | 54541 |
| DDG-118 | PROPULSION | 54542 |
| DDG-118 | AUXILIARY | 54543 |
| DDG-118 | SONAR | 54544 |
| DDG-118 | C2 | 54545 |
| DDG-118 | NAV | 54546 |
| DDG-119 USS Daedalus | MACHINERY | 54551 |
| DDG-119 | PROPULSION | 54552 |
| DDG-119 | AUXILIARY | 54553 |
| DDG-119 | SONAR | 54554 |
| DDG-119 | C2 | 54555 |
| DDG-119 | NAV | 54556 |
| DDG-120 USS Ariadne | MACHINERY | 54561 |
| DDG-120 | PROPULSION | 54562 |
| DDG-120 | AUXILIARY | 54563 |
| DDG-120 | SONAR | 54564 |
| DDG-120 | C2 | 54565 |
| DDG-120 | NAV | 54566 |
| Flagship UUV nodes | OWN SYSTEMS | 54321 |
| Flagship UUV nodes | CONTACTS / AIS | 54322 |

---

## Primary run path — one command

```bash
# Bring up the full strike group: MLflow + 9 registered models + 2 UUV nodes
# + 3 destroyers (18 containers), all live-fed, API on :8501.
bash deploy/strike_group_up.sh

# Then in a second terminal:
cd frontend/ui && npm run dev
# Open http://localhost:5173 → select "STRIKE GROUP"

# Tear down:
bash deploy/strike_group_down.sh
```

`strike_group_up.sh` handles the full sequence:
1. Node-3 MLflow `:5050` (starts if not running)
2. Register all 9 subsystem + AE models `@production` (skip with `--fast` if already registered)
3. Two UUV Pi-emulation nodes (`deploy/pi-emulation/up.sh --feed`)
4. Three destroyer hulls via `deploy/ship-emulation/up.sh --fleet --feed` (18 containers, per-hull phase/seed offset)
5. Demo API on `:8501` (`/api/destroyer`, `/api/state`, `/api/mlflow`, `/api/fleet`)

The demo also includes a second launch script for the tamper-evident records and fleet flywheel:

```bash
bash deploy/demo_up.sh   # pre-populates tamper-evident records + flywheel + preflight checks
```

Run both before a high-stakes demo.

---

## The 5–7 beats (what to say + do)

### Beat 1 — "Three ships. Eight systems each. One picture." *(0:00)*
**Say:** *"This is a destroyer strike group — three hulls, 24 onboard subsystems, each with its own model, its own container, its own alert channel. One watch officer in command of the flagship. Every subsystem isolated, low-RAM, airgap-capable."*
**Do:** sweep the Strike Group scene. Point at the three destroyer cards (DDG-118/119/120) showing all systems green. Point at the TACTICAL CONTACTS MAP — ~52 AIS contacts, the own-ship formation triangulated. Point at the record spine: **CHAIN VERIFIED · PASS**.

---

### Beat 2 — "Each subsystem has its own brain." *(0:45)*
**Say:** *"These aren't cloud calls. Each subsystem runs its own detector onboard — low-RAM, airgap-capable, fits a 4 GB Raspberry Pi. Theseus ships this on edge hardware, not a server farm."*
**Do:** show a live scored feed from the flagship SONAR node:
```bash
curl http://127.0.0.1:54544/history | jq '.[-1]'
```
Point at `active_anomaly_score: 0.21` (normal) in the JSON. No internet, no cloud dependency visible. Note the per-hull phase offset: the sister hulls are live and scoring independently — `docker ps` shows all 18 containers running.

---

### Beat 3 — "It sees what the watch officer can't." *(1:30 — anomaly beat)*
**Say:** *"That contact just jumped faster than physics allows. The system flags it cold-start — no historical database, no pre-labeled training set. It explains the flag in plain language so the officer can decide."*
**Do:** point at the TACTICAL CONTACTS MAP. Four AIS contacts are flagged: a POSITION JUMP, a LOITER, a SPOOF signature, and a DARK GAP. Click the **POSITION JUMP** alert in the CIC. Show the explanation (which sensor channel deviated, by how many σ). Leaf count on the record spine: unchanged — no decision yet.

---

### Beat 4 — "The human decides. It's provable." *(2:15 — climax)*
**Say:** *"Nothing is automatic. The watch officer accepts or overrides. That decision is sealed into the record — forever, tamper-evident, with the officer's identity and the model version that drove it. That's the accreditation evidence."*
**Do:** click **ACCEPT** → watch a new **HUMAN DECISION** leaf seal into the spine. Leaf count ticks up. **CHAIN VERIFIED · PASS** holds.

---

### Beat 5 — "Now cut the cord." *(3:00 — DDIL beat)*
**Say:** *"At sea you lose the link. Watch what happens."*
**Do:** stop the MLflow registry process:
```bash
# kill MLflow (simulates losing the shore link)
pkill -f "mlflow server" 2>/dev/null || true
```
Narrate:
- All 18 containers keep serving their **last-good** in-memory models — scores keep flowing on every hull.
- The signed-delta sync animation on the shore-fleet-brain panel shows "LAST GOOD — DDIL" state.

**Say:** *"Under denied comms, every container holds its last-good model and keeps scoring. The ship doesn't go blind — it keeps watching."*

Restart MLflow when done:
```bash
bash deploy/mlflow/run.sh
```

---

### Beat 6 — "The provenance gate rejects the poisoned delta." *(3:45 — the differentiator)*
**Say:** *"This is the moat. Federated learning has two killers: model poisoning and 'you can't accredit a model that changes.' Theseus kills both."*
**Do:** show the provenance gate panel in the CIC. An unattested delta — `keyid` not in the trust registry — is refused by the shore brain with a **REJECTED** leaf (red). The signed delta from a trusted hull sits beside it as a **ACCEPTED** leaf (green). Both have timestamps and model version hashes. Auditor-grade.

**Say:** *"A captured node can send a delta. It cannot forge the attestation chain. The fleet brain merges only what's signed and eval-gated. That's how fleet learning stays accreditable under denied comms."*

---

### Beat 7 — "And it deploys on real hull-grade rails." *(4:30 — close)*
**Say:** *"This isn't a laptop toy. It deploys on Defense Unicorns UDS — the same accredited airgap rails the Navy uses. Signed bundle, full SBOM, machine-enforced human-in-command. The record this generates is the ATO evidence package — the AO doesn't re-verify a frozen model; they verify the pipeline's provenance. That gap closes today with Theseus."*
**Do:** show `kubectl get pods` (Theseus on uds-core) + the Pepr denial of a violating pod + cosign signature. Refer to `deploy/UDS_DEPLOY_EVIDENCE.md` as the leave-behind.

---

## Pre-flight checklist (run the morning of)

- [ ] `bash deploy/strike_group_up.sh` runs clean — watch the 6-step output, all ✓
- [ ] All 9 models registered: check `http://localhost:5050` → 9 models `@production`
- [ ] `docker ps | grep theseus` shows 18 subsystem containers running
- [ ] `curl http://127.0.0.1:54321/health` and `:54322/health` — UUV nodes healthy
- [ ] `curl http://localhost:8501/api/destroyer` → non-empty JSON with 3 hulls
- [ ] `cd frontend/ui && npm run dev` → `:5173` loads, header reads **LINK LIVE**
- [ ] Strike Group scene: destroyer cards + tactical contacts map + provenance gate all visible
- [ ] Confirm ~52 AIS contacts on the map, 4 flagged (spoof/jump/loiter/dark-gap), 3 own-ships in formation
- [ ] `python3 -m pytest tests/ -q` → all green
- [ ] Beat 5 DDIL test: kill MLflow → containers hold last-good → restart MLflow → live scores resume
- [ ] 60s fallback recording on the demo machine
- [ ] Bookmark `http://localhost:5173` full-screen on the presentation display

---

## Appendix — manual bring-up steps (if strike_group_up.sh fails)

### Step 1 — Start the fleet brain
```bash
bash deploy/mlflow/run.sh
# Binds :5050. Wait for: "Listening on http://0.0.0.0:5050"
curl http://localhost:5050/health   # expect 200
```

### Step 2 — Register subsystem models
```bash
# 6 subsystem models (CBM/C-MAPSS/MetroPT/sonar/c2/nav):
MLFLOW_TRACKING_URI=http://localhost:5050 \
  deploy/mlflow/.venv312/bin/python models/subsystems/train_subsystems.py

# UUV autoencoder (theseus-uuv):
MLFLOW_TRACKING_URI=http://localhost:5050 \
  deploy/mlflow/.venv312/bin/python models/uuv/register_uuv_ae.py

# Verify (expect 9 names):
curl -s http://localhost:5050/api/2.0/mlflow/registered-models/search | \
  python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['registered_models']]"
```

### Step 3 — UUV Pi-emulation nodes
```bash
bash deploy/pi-emulation/up.sh --feed
curl http://127.0.0.1:54321/health   # {"status":"ok","model":"uuv1_anomaly_deploy@production"}
curl http://127.0.0.1:54322/health   # {"status":"ok","model":"uuv2_anomaly_deploy@production"}
```

### Step 4 — Three-hull destroyer strike group
```bash
bash deploy/ship-emulation/up.sh --fleet --feed --interval=2
# 18 containers on DDG-118/119/120, each hull offset in phase/seed.
```

### Step 5 — API
```bash
python3 demo/api.py --port 8501
curl http://localhost:8501/api/destroyer   # 3-hull JSON
```

### Step 6 — UI
```bash
cd frontend/ui && npm run dev
# http://localhost:5173 → "STRIKE GROUP"
```

---

## Language discipline (carry into the room)
- "Recommended intervention, human always in command" — never "the fleet updates itself"
- "Improves safely — every update eval-gated, attested, and rollback-protected"
- "Prototype at this scale; production path is a program-office sponsor + ATO inheritance via UDS"
- "cATO-for-AI: you accredit the pipeline's provenance, not the frozen weights"
- "Auxiliary AUC 0.68 — honest; MetroPT is a compressor proxy, not ship-grade HM&E data"
