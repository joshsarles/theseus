# THESEUS

**The accreditable fleet-learning layer for unmanned maritime vehicles under DDIL — human always in command.**

Unmanned vehicles (UUVs) operate cut off from comms (**DDIL**: denied, degraded, intermittent, limited). Each vehicle has to learn from what it sees *locally* — and when a fleet of them surfaces, their hard-won improvements must be combined **safely and accountably**, because you cannot recall a bad model from a submerged vehicle. **THESEUS is that layer:** each UUV learns onboard; a **fleet node** merges the improvements as **model deltas (never raw data)** through a **provenance-gated, eval-gated, signed** merge; and **every model update + human decision is sealed in a tamper-evident, standards-based record (in-toto/DSSE + Ed25519, NIST OSCAL)** an accreditor can trust. *Tesla-FSD-for-a-UUV-fleet — but DDIL-native and accreditable.*

The Navy's data engine (DECK) *opens* that learning loop; nothing today closes it onboard, coordinates models across a fleet, or makes a *changing* model accreditable. **That's the open lane THESEUS fills.**

> *Like the Ship of Theseus — every plank can be replaced and she's still herself, because the brain that runs her is one.*

Built at Warhacker (Jun 16–19 2026) by a team of NAVSEA + retired Navy/Marine engineers (Force AI). AGPL-3.0.

## The architecture (3 nodes)
- **Node 1 + Node 2 = the UUVs** — Raspberry Pi 5 (4 GB) onboard brains; learn locally, airgapped (DDIL); run lightweight ONNX models onboard.
- **Node 3 = the fleet coordinator** — hosts the **MLflow** model registry + the **UI**; aggregates the UUVs' improvements, **eval-gates** the best, pushes it back down.
- **The flywheel:** learn local → push **signed deltas** → **merge** (a captured/poisoned node is *rejected*) → **eval-gate** (a worse model never ships) → push back. Every step **sealed + accreditable** (cATO-for-AI).

## What's real today (verifiable in this repo)
| Capability | Where | Try it |
|---|---|---|
| Tamper-evident **signed record** (hash chain + Merkle + Ed25519 + in-toto/DSSE) | `referee/chain.py` | `python3 -m pytest tests/` |
| **Fleet-learning flywheel** — provenance-gated merge, poison **rejected**, eval-gate | `fleet/` | `bash fleet/run_miniature.sh` |
| **DDIL** edge loop (learn → update → disconnect → last-good / rollback) | `demo/`, `serve/` | `bash demo/run.sh` |
| **Digital-twin UI** (OPERATIONS + FLEET LEARNING scenes) | `frontend/ui/` | `npm install && npm run dev` |
| Real **airgap UDS deploy** (Zarf + SBOM + cosign + Pepr admission) | `deploy/` | see `deploy/UDS_DEPLOY_EVIDENCE.md` |
| Edge inference (ONNX, fits a 4 GB Pi) | `models/` | — |

## Run / review it
```bash
bash deploy/demo_up.sh        # brings the whole stack to GO (record + API + preflight gate)
bash deploy/preflight.sh      # GO/NO-GO — refuses a broken or silently-mock stack
bash fleet/run_miniature.sh   # the fleet-learning flywheel, end to end
python3 -m pytest tests/      # the test suite (21)
```
UI → `http://localhost:5173` (needs the state API on `:8501`, which `demo_up.sh` starts).

## Where to look (judges + new teammates)
- **`docs/JUDGE_REVIEW.md`** — guided walkthrough (review the system without a live demo)
- **`docs/vision/UUV_FLEET_ARCHITECTURE.md`** — the locked plan (topology + the data-honesty fork)
- **`docs/vision/FLEET_LEARNING_VISION.md`** — the vision · **`docs/research/DECK_BLUE_OCEAN.md`** — the open lane
- **`docs/ONBOARDING.md`** — get running in ~20 min · **`ROADMAP.md`** — state + update log

## Rails (carried into everything)
Human always in command — never autonomous · **all-real** (proxies + in-progress labeled as such) · tamper-**evident**, not tamper-proof · integrate-not-replace · **data honesty** — what the platform *watches* (surface contacts; AIS, real) vs the platform's *own* UUV systems (real UUV telemetry, not jet-engine proxies) are kept separate · **OPSEC**: no real names / commands in this public repo.
