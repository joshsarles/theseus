# THESEUS — Judge Review (guided walkthrough)

*Review the system without a live demo. Every claim below is reproducible from this repo — the commands and their real output are shown. ~10 minutes.*

---

## In one line
**THESEUS is the accreditable fleet-learning layer for unmanned maritime vehicles under DDIL.** UUVs learn locally while cut off; a fleet node merges their improvements (**model deltas, never raw data**) through a **provenance-gated, eval-gated, signed** merge; every step is sealed in a **tamper-evident, standards-based record** an accreditor can trust. *Tesla-FSD-for-a-UUV-fleet — DDIL-native and accreditable.* The Navy's DECK opens that loop; nothing closes it onboard, coordinates models across a fleet, or makes a *changing* model accreditable — **that's the lane.**

## Fastest path to "I believe it" (3 commands)
```bash
bash deploy/demo_up.sh        # → GO (brings the whole stack up + runs the preflight gate)
bash fleet/run_miniature.sh   # → the fleet-learning flywheel, end to end
python3 -m pytest tests/      # → 21 passed
```

---

## Beat 1 — The fleet-learning flywheel (the hero) · `fleet/run_miniature.sh`
**What it proves:** two UUVs each learn locally on disjoint data, push **signed model deltas** up, and the fleet node merges them **safely** — rejecting a poisoned delta and refusing a merged model that would regress.

**Real output (abridged):**
```
Signing : Ed25519 DSSE
local train RMSE : 0.029348   (vs baseline 0.126955)   ← UUV-1 learned locally
local train RMSE : 0.027021   (vs baseline 0.146845)   ← UUV-2 learned locally
PHASE 2: POISON INJECTION — forged delta signed by a key NOT in the trust registry
PHASE 3: PROVENANCE GATE + FEDAVG + EVAL GATE
   [ MACHINERY ]  ACCEPTED  OK
   [ CONTACTS  ]  ACCEPTED  OK
   [ POISON_NODE] REJECTED  unknown ship keyid='POISON_NODE' (no .pub in key_dir)
   Merging 2 accepted delta(s) (FedAvg, weights by n_samples [300, 300])
   Incumbent RMSE 0.031816 → merged model PASSES the eval gate → accepted
   Chain verify: PASS
```
**Why it matters:** this is the whole thesis in 30 seconds — **federated learning** (deltas, not raw sonar) + **Byzantine/provenance defense** (a captured UUV can't poison the fleet) + a **pre-deployment eval-gate** (you can't recall a bad model from a submerged vehicle, so a regression never ships). Code: `fleet/fleet_brain.py` (merge + gates), `fleet/signing.py` (Ed25519 DSSE), `fleet/ship_node.py` (local learning).

## Beat 2 — The tamper-evident record (the moat) · `referee/chain.py`
**What it proves:** every model update + human decision is sealed in a hash-chained, **Ed25519-signed**, in-toto/DSSE-attested record that **verifies offline** and **snaps** if a single byte changes.
```bash
python3 -m pytest tests/ -q          # 21 passed — includes verify + tamper-snap tests
```
The fleet record above ends in `Chain verify: PASS`; the miniature also demonstrates a tamper on a copy → the chain SNAPS. **This is cATO-for-AI:** you accredit the *pipeline's provenance*, not frozen weights — which is exactly what lets a *learning* system stay accreditable. Code: `referee/chain.py` (`verify_dir()`), attestations in `referee/keys/`.

## Beat 3 — The DDIL edge loop · `demo/`, `serve/`
**What it proves:** a vehicle keeps working **disconnected** — learn → update the local model → lose comms → serve last-good → reconnect → take a signed update. Cold-start, no historical DB (works in a novel OPAREA day one). Code: `demo/run.sh`, the DDIL beat in `deploy/ddil_beat.sh`, edge serve in `serve/`.

## Beat 4 — Real airgap deploy · `deploy/`
**What it proves:** the whole thing ships to a disconnected cluster from **one signed bundle** with compliance evidence generated as it runs — **Zarf** package + **SBOM** + **cosign** signature + live **Pepr** admission (policies bound to the sealed record) + **NIST OSCAL** emit. Evidence: `deploy/UDS_DEPLOY_EVIDENCE.md`, policies in `deploy/uds/pepr/`, OSCAL in `lula/`.

## Beat 5 — The digital-twin UI · `frontend/ui/`
**What it proves:** a watch-grade picture, read **straight from the record**. Two scenes: **OPERATIONS** (the vehicle/ship twin with live subsystem state) and **FLEET LEARNING** (the flywheel — deltas, the provenance gate rejecting the poisoned node, the eval-gate, the accreditation panel).
```bash
cd frontend/ui && npm install && npm run dev   # → http://localhost:5173  (API on :8501 via demo_up.sh)
```

---

## What's real vs. in-flight (we say it out loud)
- **Real + verified (in this repo, on `main`):** the signed record, the fleet-learning flywheel (poison rejected, eval-gate, verifies), the DDIL edge loop, the airgap UDS deploy (Zarf/SBOM/cosign/Pepr/OSCAL), ONNX edge inference (fits a 4 GB Pi), the digital-twin UI, 21 tests.
- **The contact-detection number (NV063, AIS Pattern-of-Life):** precision **0.57** / recall **0.89** / false-alarm **0.15** / F1 **0.70** on an analyst-labeled set of **n=50** — an honest early number, not a leaderboard claim. Code: `demo/ais_pol.py`, eval in `eval/`.
- **In-flight (the team's last-day lanes):** the real **UUV-shaped** dataset + a **sequence-autoencoder** model on it (registers in MLflow as `theseus-uuv`); the live **MLflow** server on Node 3; the 2 Raspberry Pis as live UUV nodes. *The flywheel runs today on the miniature; these make it the full hardware loop.*

## The data-honesty fork (important — and we keep it honest)
- **Framing A — what the platform WATCHES:** surface/air contact Pattern-of-Life. Data is correct (AIS).
- **Framing B — the platform's OWN UUV systems** (the anchor): onboard subsystem health. The machinery datasets here are **proxies** (gas turbine / turbofan) — the real UUV model trains on genuine UUV-shaped telemetry (BlueROV2/glider/sim). *We do not call a jet engine a UUV.*

## Why it scores the rubric
- **Mission impact / innovation:** the *missing* fleet-MLOps + accreditation layer for distributed maritime autonomy — an open lane (no named Navy program; CDAO's AI-assessment framework not due until ~2027).
- **Portability / readiness:** real airgap UDS bundle + compliance evidence (about half the rubric) — already built, not a slide.
- **Trustworthy AI:** the tamper-evident signed record + provenance-gated merge + eval-gate — "trusted AI/autonomy" demonstrated, not asserted.
- **Resourceful / team:** a real engine in stdlib-light glue, built by NAVSEA + retired-Navy/Marine engineers for themselves.

## Read next
`docs/vision/UUV_FLEET_ARCHITECTURE.md` (the locked plan) · `docs/vision/FLEET_LEARNING_VISION.md` (the vision) · `docs/research/DECK_BLUE_OCEAN.md` (the open lane) · `ROADMAP.md` (state + log).
