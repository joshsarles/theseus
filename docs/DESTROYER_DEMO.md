# THESEUS — Strike Group Demo Script
*Presenter-facing. 5–7 beats, ~5 minutes. Everything here runs on the Mac (Node 3) — no Pis required. Rehearse the full sequence once before judges arrive.*

---

## The narrative

**A destroyer is a self-contained city.** Machinery keeps the lights on. Propulsion drives the shaft. Navigation holds the track. Damage control watches the hull. Electronic warfare listens for threats. Sonar hunts below the surface. Power management balances the grid. Contacts tracks what's out there. Each of these is a distinct system, on a distinct bus, run by a distinct crew.

Theseus mirrors that architecture: **each subsystem runs its own onboard ML model in its own container**, isolated, low-RAM, inference-only at the edge. A human watch officer is always in command — the system recommends, the officer decides, and every decision is sealed in a tamper-evident record.

When the ship is **not in a contested environment**, it syncs **model deltas — never raw sensor data** — to the fleet brain ashore (Node 3 MLflow in the demo). The fleet brain merges only the **provenance-attested** updates. A captured node can't poison the fleet: its delta is rejected at the gate because it lacks the signed attestation chain. A frozen model can't hide: every update is eval-gated before it promotes. The result is a fleet that keeps learning at sea — **Tesla-fleet-style, but human-authorized, eval-gated, and provenance-attested**. That sealed record is not a side feature: it is what makes fleet learning **accreditable** — a cATO-for-AI path, in the AO's own OSCAL language.

---

## The 8-subsystem table

| # | Subsystem | Canonical dataset | Model type | Edge node | Anomaly score (normal / anomaly) |
|---|-----------|------------------|------------|-----------|----------------------------------|
| 1 | **MACHINERY / HM&E** | UCI #316 gas-turbine decay (real compressor data) | Streaming z-score · ONNX CBM | `uuv1-node` :54321 | ~0.2 / ~0.9 |
| 2 | **CONTACTS / AIS PoL** | MarineCadastre AIS (real vessel tracks, Gulf + Ushant cross-validation) | Cold-start Pattern-of-Life | `uuv2-node` :54322 | n/a — position-jump score |
| 3 | **PROPULSION** | UUV nav telemetry (BlueROV2/ArduSub) | Sequence autoencoder · ONNX-int8 | `uuv1-node` co-located | via `theseus-uuv` model |
| 4 | **POWER / ELECTRICAL** | UUV combined sensor dataset (25 labeled anomalies) | RunningZScoreDetector (per-feature Welford) | `uuv2-node` co-located | ~0.2 / ~0.9 |
| 5 | **NAVIGATION / IMU** | UUV nav telemetry, latency + seq-gap features | `train_c2.py` anomaly detector | Node 3 receiver | P@25 0.96 / F1 0.96 |
| 6 | **DAMAGE CONTROL** | UUV sonar / water-sensor dataset (pressure, temp, salinity anomalies) | Streaming z-score (sonar channels) | `uuv2-node` co-located | per-channel σ |
| 7 | **C2 LINK / COMMS** | Real UUV C2 telemetry (failed-integrity flags, 20s latency spikes, ABORT_MISSION events) | `train_c2.py` · registered `uuv1_anomaly_deploy@production` | Node 3 + `uuv1-node` | P@25 0.96 / AUC 0.9995 |
| 8 | **ELECTRONIC WARFARE / SENSOR FUSION** | AIS + sonar combined (multi-source `train_river_uuv.py`) | River multi-source HST fusion | Node 3 (Tier-1) | pending relative threshold |

*For the demo, Subsystems 1 + 2 are live-running containers (uuv1-node / uuv2-node). Subsystems 3–8 share the same registered models and receiver pipeline — they represent the full scope the architecture targets. Be honest with judges: "live containers for 1 + 2; architecture proven, remaining subsystems same spine."*

---

## Exact run steps (in order)

### Step 1 — Start the fleet brain (Node-3 MLflow)
```bash
bash /path/to/theseus/deploy/mlflow/run.sh
# Binds :5050. Allowed hosts configured for host.docker.internal + RFC-1918.
# Wait for: "Listening on http://0.0.0.0:5050"
curl http://localhost:5050/health   # expect 200
```

### Step 2 — Register subsystem models
*The subsystem models must be in the MLflow registry before the containers load them.*
```bash
# Register the MACHINERY + CONTACTS + C2 detectors (py3.12 venv — required for cross-Pi cloudpickle compat):
MLFLOW_TRACKING_URI=http://localhost:5050 \
  deploy/mlflow/.venv312/bin/python serve/receiver/register_pickle_model.py
# Verify both aliases resolve:
curl http://localhost:5050/api/2.0/mlflow/registered-models/search | \
  python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['registered_models']]"
# Expect: uuv1_anomaly_deploy, uuv2_anomaly_deploy
```

### Step 3 — Bring up the ship containers
```bash
bash deploy/pi-emulation/up.sh --feed
# Starts uuv1-node :54321 (MACHINERY) + uuv2-node :54322 (CONTACTS) on the fleet bridge.
# --feed starts one synthetic sensor stream per node (1 record / 30s; use --interval=2 for a livelier demo).
# Wait for both health checks:
curl http://127.0.0.1:54321/health   # {"status":"ok","model":"uuv1_anomaly_deploy@production"}
curl http://127.0.0.1:54322/health   # {"status":"ok","model":"uuv2_anomaly_deploy@production"}
```

### Step 4 — Start the API
```bash
python3 demo/api.py --port 8501
# The CIC frontend reads from :8501. Confirm the feed is live (not the mock fixture):
curl http://localhost:8501/api/health   # must return {"connection":"live"}
```

### Step 5 — Start the CIC dashboard
```bash
cd frontend/ui && npm run dev
# Opens on http://localhost:5173
# Open in a browser, full-screen. Confirm the top header reads "LINK LIVE" (amber dot).
```

### Step 6 — Open the Strike Group scene
- In the CIC dashboard, select **Strike Group** view.
- Verify the systems column shows MACHINERY + CONTACTS as **ACTIVE** (green pulse).
- Verify the **CHAIN VERIFIED · PASS** indicator on the record spine (right column).
- Point at the tactical picture (real AIS contacts from MarineCadastre data).

---

## The 5–7 beats (what to say + do)

### Beat 1 — "One ship, eight systems." *(0:00)*
**Say:** *"This is a destroyer — a self-contained city. Eight onboard systems, each with its own model, its own container, its own alert channel. One watch officer in command of all of it."*
**Do:** sweep the systems column left to right. Point at the record spine: **CHAIN VERIFIED · PASS**.

---

### Beat 2 — "Each subsystem has its own brain." *(0:45)*
**Say:** *"These aren't cloud calls. Each subsystem runs its own detector onboard — low-RAM, airgap-capable, fits a 4 GB Raspberry Pi. Theseus ships this on edge hardware, not a server farm."*
**Do:** show the live scored feed from uuv1-node: `curl http://127.0.0.1:54321/history | jq '.[-1]'`. Point at `active_anomaly_score: 0.21` (normal) in the JSON. No internet, no cloud dependency visible.

---

### Beat 3 — "It sees what the watch officer can't." *(1:30 — anomaly beat)*
**Say:** *"That contact just jumped faster than physics allows. Cold-start — no historical database, no pre-labeled training set. It explains the flag in plain language so the officer can decide."*
**Do:** click the **POSITION JUMP** alert in the CIC. Show the explanation (grounded in the detection, generated by the local LLM running fully airgapped). Leaf count on the record spine: unchanged — no decision yet.

---

### Beat 4 — "The human decides. It's provable." *(2:15 — climax)*
**Say:** *"Nothing is automatic. The watch officer accepts or overrides. That decision is sealed into the record — forever, tamper-evident, with the officer's identity and the model version that drove it. That's the accreditation evidence."*
**Do:** click **ACCEPT** → watch a new **HUMAN DECISION** leaf seal into the spine. Leaf count ticks up. **CHAIN VERIFIED · PASS** holds.

---

### Beat 5 — "Now cut the cord." *(3:00 — DDIL beat)*
**Say:** *"At sea you lose the link. Watch what happens."*
**Do:** run `bash deploy/ddil_beat.sh` (or physically pull the wifi). Narrate:
- Both nodes keep serving their **last-good** models — scores keep flowing.
- A signed model delta arrives in a bundle from the fleet brain.
- Theseus promotes it, seals the update into the record.
- Now inject a poisoned delta — one with a tampered weight hash.
- **The provenance gate rejects it.** The previous model stays in service. The record logs the rejection.

**Say:** *"A captured node can send a delta. It cannot forge the attestation chain. The fleet brain merges only what's signed and eval-gated. That's how fleet learning stays accreditable under denied comms."*

---

### Beat 6 — "The provenance gate rejects the poisoned delta." *(3:45 — the differentiator)*
**Say:** *"This is the moat. Federated learning has two killers: model poisoning and 'you can't accredit a model that changes.' Theseus kills both. Provenance-gated merge stops poisoning. The sealed record — in OSCAL, in in-toto/SLSA — is what an AO consumes for a cATO-for-AI. Not frozen weights. The pipeline's provenance."*
**Do:** show the rejected delta log entry in the record spine (red REJECTED leaf vs green ACCEPTED leaf beside it). Both have timestamps and the model version hashes. Auditor-grade.

---

### Beat 7 — "And it deploys on real hull-grade rails." *(4:30 — close)*
**Say:** *"This isn't a laptop toy. It deploys on Defense Unicorns UDS — the same accredited airgap rails the Navy uses. Signed bundle, full SBOM, machine-enforced human-in-command. The record this generates is the ATO evidence package — the AO doesn't re-verify a frozen model; they verify the pipeline's provenance. That gap closes today with Theseus."*
**Do:** show `kubectl get pods` (Theseus on uds-core) + the Pepr denial of a violating pod + cosign signature. Refer to `deploy/UDS_DEPLOY_EVIDENCE.md` as the leave-behind.

---

## Pre-flight checklist (run the morning of)
- [ ] `bash deploy/mlflow/run.sh` → `:5050/health` 200
- [ ] Both models registered: `uuv1_anomaly_deploy@production` + `uuv2_anomaly_deploy@production`
- [ ] `bash deploy/pi-emulation/up.sh --feed` → both nodes healthy, scores flowing
- [ ] `python3 demo/api.py --port 8501` → `/api/health` returns `connection: live`
- [ ] `cd frontend/ui && npm run dev` → `:5173` loads, header reads **LINK LIVE**
- [ ] `python3 -m pytest tests/ -q` → all green
- [ ] `bash deploy/ddil_beat.sh` → all PASS (run with internet OFF)
- [ ] 60s fallback recording on the demo machine (Aaron)
- [ ] Bookmark `http://localhost:5173` full-screen on the presentation display

## Language discipline (carry into the room)
- "Recommended intervention, human always in command" — never "the fleet updates itself"
- "Improves safely — every update eval-gated, attested, and rollback-protected"
- "Prototype at this scale; production path is a program-office sponsor + ATO inheritance via UDS"
- "cATO-for-AI: you accredit the pipeline's provenance, not the frozen weights"
