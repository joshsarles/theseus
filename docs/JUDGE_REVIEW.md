# THESEUS — Judge Review (guided walkthrough)

*Review the system without a live demo. Every claim below is reproducible from this repo — the commands and their real output are shown. ~10 minutes.*

---

## In one line
**THESEUS is the accreditable fleet-learning layer for unmanned maritime vehicles under DDIL.** UUVs learn locally while cut off; a fleet node merges their improvements (**model deltas, never raw data**) through a **provenance-gated, eval-gated, signed** merge; every step is sealed in a **tamper-evident, standards-based record** an accreditor can trust. *Tesla-FSD-for-a-UUV-fleet — DDIL-native and accreditable.* The Navy's DECK opens that loop; nothing closes it onboard, coordinates models across a fleet, or makes a *changing* model accreditable — **that's the lane.**

**Why it changes the mission:** a frozen-weight ATO breaks the moment a model improves — so fielded Navy AI either never updates or falls out of accreditation. THESEUS makes the **pipeline** the accreditation boundary, not the weights, so a fleet that *learns at sea stays accredited*. Concretely, today: one shore brain coordinates a **3-hull strike group** (live: `/api/destroyer` → DDG-118/119/120); the per-hull architecture is identical, so scaling to a fleet of N is **+1 signed delta per hull, not +1 model to re-accredit**. And a poisoned delta from a captured UUV is **rejected at the gate** (live: `POST /api/fleet/inject` → `deltas_rejected: 1`), so one compromised vehicle cannot move the model every other hull steers by.

## Fastest path to "I believe it"
```bash
pip install -r requirements.txt   # numpy + cryptography + scikit-learn (the fleet-learning + signing layer)
bash deploy/demo_up.sh            # → GO (stages the record, starts the :8501 API, runs the preflight gate)
bash fleet/run_miniature.sh       # → the fleet-learning flywheel, end to end
uv run pytest tests/ -q           # → 21 passed   (uv.lock pins a byte-reproducible env)
```
*`demo_up.sh` is the single entry point — it stages the record the gate checks (run it before `preflight.sh`). The explain beat wants a local llama-server (qwen2.5-1.5b) on :8080; without one, run `SKIP_EXPLAINER=1 bash deploy/preflight.sh` and the deterministic template stands in.*

**See the two hero proofs live (with the strike group up — `bash deploy/strike_group_up.sh`):**
```bash
curl -s -X POST localhost:8501/api/fleet/inject -d '{}'   # forged delta from an unregistered key → deltas_rejected:1,
                                                          # 2 trusted deltas merge, RMSE improves past the eval gate,
                                                          # the chain RE-VERIFIES (leaf_count climbs, verify PASS)
curl -s localhost:8501/api/oscal                          # the SAME sealed events as NIST OSCAL 1.1.3 assessment-results:
                                                          # 4 SP 800-53 controls satisfied (incl. SI-7 = the poison refused),
                                                          # signed+attested coverage — the package an AO ingests
```
*In the UI (STRIKE GROUP scene) these are one button: fire the forged delta, watch the gate reject it and the OSCAL controls re-verify in lockstep.*

---

## Beat 1 — The fleet-learning flywheel (the hero) · `fleet/run_miniature.sh`
**What it proves:** two simulated UUVs — node IDs **MACHINERY** (UUV-1) and **CONTACTS** (UUV-2), two range strata of one contact-estimation task — each learn locally on **disjoint, deterministic-synthetic** data, push **signed model deltas** up, and the fleet node merges them **safely** — rejecting a poisoned delta and refusing a merged model that would regress. *(Data is synthetic + seed-fixed; the mechanics on top — signing, the gates, FedAvg, the hash chain — are real and what you're verifying.)*

**Real output (abridged):**
```
Signing : Ed25519 DSSE
local train RMSE : 0.029348   (vs baseline 0.126955)   ← MACHINERY (UUV-1) learned locally
local train RMSE : 0.027021   (vs baseline 0.146845)   ← CONTACTS (UUV-2) learned locally
PHASE 2: POISON INJECTION — forged delta signed by a key NOT in the trust registry
PHASE 3: PROVENANCE GATE + FEDAVG + EVAL GATE
   [ MACHINERY ]  ACCEPTED  OK
   [ CONTACTS  ]  ACCEPTED  OK
   [ POISON_NODE] REJECTED  unknown ship keyid='POISON_NODE' (no .pub in key_dir)
   Merging 2 accepted delta(s) (FedAvg, weights by n_samples [300, 300])
   Incumbent RMSE 0.031816 → merged model PASSES the eval gate → accepted
   Chain verify: PASS
```
**Why it matters:** this is the whole thesis in 30 seconds — **federated learning** (deltas, not raw sonar) + **provenance-gated defense** (an unattested/unregistered node's delta is rejected — and the Ed25519 signature **binds the actual model weights** via a signed `model_params_hash`, so a *captured* node with a valid key that swaps the weights is rejected too; Byzantine-robust aggregation is the named roadmap upgrade) + a **pre-deployment eval-gate** (you can't recall a bad model from a submerged vehicle, so a regression never ships). Code: `fleet/fleet_brain.py` (merge + gates), `fleet/signing.py` (Ed25519 DSSE), `fleet/ship_node.py` (local learning).

## Beat 2 — The tamper-evident record (the moat) · `referee/chain.py`
**What it proves:** every model update + human decision is sealed in a hash-chained, **Ed25519-signed**, in-toto/DSSE-attested record that **verifies offline** and **snaps** if a single byte changes.
```bash
python3 -m pytest tests/ -q          # 21 passed — includes verify + tamper-snap tests
```
The fleet record above ends in `Chain verify: PASS`; the miniature also demonstrates a tamper on a copy → the chain SNAPS. **This is the cATO-for-AI *mechanism*:** you accredit the *pipeline's provenance*, not frozen weights — which is exactly what lets a *learning* system stay accreditable. **The mechanism is built and demonstrable; an authorizing official signing this record as cATO evidence is the next step, not a claim made here.** Code: `referee/chain.py` (`verify_dir()`), attestations in `referee/keys/`. *The record spine is **stdlib-only** — `referee/chain.py` imports zero third-party packages at module level (crypto is loaded lazily inside the signing functions), so the chain seals and verifies on a bare Python install; prove it: `python3 -c "import referee.chain"` with nothing installed. The MLflow / serve / edge layers compose heavier best-of-breed (mlflow, torch, onnxruntime, river) on top — that layering, not a monolith, is the resourceful story.*

## Beat 3 — The DDIL edge loop · `demo/`, `serve/`
**What it proves:** a vehicle keeps working **disconnected** — learn → update the local model → lose comms → serve last-good → reconnect → take a signed update. Cold-start, no historical DB (works in a novel OPAREA day one). Code: `demo/run.sh`, the DDIL beat in `deploy/ddil_beat.sh`, edge serve in `serve/`.

## Beat 4 — Real airgap deploy · `deploy/`
**What it proves:** THESEUS deploys to a disconnected k3d cluster from a real **Zarf** airgap bundle (image side-loaded, `imagePullPolicy: Never`) with an **SBOM** + an offline-verified **cosign** signature, and **live Pepr admission** that DENIED 4 policy-violating pods and ADMITTED 2 compliant ones. A real **OSCAL emit path** (`deploy/lula/record_to_oscal.py`) projects the actual sealed record onto SP 800-53. **Honest scope:** full **UDS Core** (Istio mTLS / Keycloak / the Package-CR operator) needs a registry-mirrored host and is **not deployed here**, and the Lula control-validation is partial — the full REAL-vs-PENDING breakdown is in `deploy/UDS_DEPLOY_EVIDENCE.md`. Policies in `deploy/uds/pepr/`.

## Beat 5 — The digital-twin UI · `frontend/ui/`
**What it proves:** a watch-grade picture, read **straight from the record**. Three scenes: **OPERATIONS** (the twin with live subsystem state), **FLEET LEARNING** (the flywheel — deltas, the provenance gate rejecting the poisoned node, the eval-gate, the accreditation panel), and **STRIKE GROUP** (three-hull strike group, tactical contacts map, shore fleet-brain sync). *(The OPERATIONS 3D twin currently renders a procedural surface-warship placeholder, watermarked `DDG-CLASS · PROCEDURAL`; UUV geometry is in-flight. The live content to evaluate is the FLEET LEARNING flywheel + the record + the accreditation panel.)*
```bash
cd frontend/ui && npm install && npm run dev   # → http://localhost:5173  (API on :8501 via demo_up.sh)
```

---

## What's real vs. in-flight (we say it out loud)
- **Real + verified (in this repo, on `main`):** the signed record, the fleet-learning flywheel (on synthetic data — poison rejected, eval-gate, verifies), the DDIL edge loop, the airgap **Zarf** deploy (Zarf bundle + SBOM + cosign + live Pepr admission) + the OSCAL emit path, ONNX edge inference (fits a 4 GB Pi), the digital-twin UI, 21 tests. *(In-flight: full UDS Core — Istio/Keycloak — + complete Lula control-validation; UUV twin geometry.)*
- **The contact-detection number (NV063, AIS Pattern-of-Life — Framing A):** precision **0.69** / recall **1.0** / false-alarm **0.10** / F1 **0.82** on an analyst-labeled set of **n=50** (anomaly-enriched; pending SME validation) — an honest early number, not a leaderboard claim. **Reproduce it:** `python3 eval/score.py --pred eval/out/ais_pol_preds.csv --labels eval/curated_labels.csv` (predictions committed). Code: `demo/ais_pol.py`, eval in `eval/`.
- **The UUV C2-link anomaly detector (Framing B — REAL now):** a RunningZScoreDetector (online per-feature Welford mean/var; explainable — which sensor channel deviated, by how many σ) (`serve/receiver/`) on **genuine UUV command-link data** (`serve/receiver/data/uuv1-c2-anom.json` — failed-integrity, 20s latency spikes, ABORT_MISSION) — **precision@25 0.96 / recall 0.96 / F1 0.96 / false-alarm 1.3% / AUC 0.9995** (verified live in the :5050 registry), registered as `uuv1_anomaly_deploy` (v5), and the edge receiver pulls it. *This is the strongest detection number in the system, on the platform's OWN UUV systems — reproduce it below.* The Node-1/2 onboard brain. **Reproduce:** `bash deploy/mlflow/run.sh` then `MLFLOW_TRACKING_URI=http://localhost:5050 python3 serve/receiver/train_c2.py`.
- **theseus-uuv** (Conv1d sequence autoencoder, BlueROV2/ArduSub, ONNX, registered @production, live in its own container) is the UUV own-systems organ — AUC 0.77 (from the offline BlueROV2 eval; the live node serves a reconstruction-error anomaly score, not a logged AUC), :54547 (`uuv-ae:latest`). The 2 Raspberry Pis are kept as UUV emulation nodes; connecting to real Pis is the next hardware step.

## The data-honesty fork (important — and we keep it honest)
- **Framing A — what the platform WATCHES:** surface/air contact Pattern-of-Life. Data is correct (AIS).
- **Framing B — the platform's OWN UUV systems** (the anchor): onboard health / C2 anomaly. **Now backed by REAL UUV data** — the C2-link detector above runs on genuine UUV command-link traffic (`uuv1-c2-anom.json`). The earlier machinery datasets (gas turbine / turbofan) were **proxies** and are labeled as such; the `theseus-uuv` Conv1d autoencoder on BlueROV2/ArduSub telemetry is registered @production and live in its own container. *We do not call a jet engine a UUV.*
- **The subsystem anomaly streams (sonar / own-sensor) are synthetic-distribution** — faults injected over a fitted normal baseline, the same way the machinery proxies are. Their high AUC (e.g. sonar 0.9995) measures separability on that synthetic stream, not a real measured dataset. The two REAL detection datasets are AIS (Framing A) and the UUV C2-link (Framing B); everything else is honestly proxy/synthetic until ship-grade data lands.
- **Operating-point honesty:** `propulsion_deploy` (AUC 0.99) and `auxiliary_deploy` (AUC 0.68) are AUC-strong but **threshold-untuned** on proxy data, so their F1 at the deployed operating point is near-zero — a calibration gap, not a broken detector. We say so rather than lead with the AUC.

## Why it scores the rubric
- **Mission impact / innovation:** the *missing* fleet-MLOps + accreditation layer for distributed maritime autonomy — an open lane (no named Navy program; CDAO's AI-assessment framework not due until ~2027).
- **Portability / readiness:** real airgap UDS bundle + compliance evidence (about half the rubric) — already built, not a slide.
- **Trustworthy AI:** the tamper-evident signed record + provenance-gated merge + eval-gate — "trusted AI/autonomy" demonstrated, not asserted.
- **Resourceful / team:** a real engine in stdlib-light glue, built by NAVSEA + retired-Navy/Marine engineers for themselves.

## Read next
`docs/vision/UUV_FLEET_ARCHITECTURE.md` (the locked plan) · `docs/vision/FLEET_LEARNING_VISION.md` (the vision) · `docs/research/DECK_BLUE_OCEAN.md` (the open lane) · `ROADMAP.md` (state + log).
