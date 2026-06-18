# THESEUS — Docs Index
*The map. Start at the top.*

## Start here
- **`../README.md`** — the front door (what THESEUS is + what's real + how to run it).
- **`JUDGE_REVIEW.md`** — **guided walkthrough** to review the system without a live demo (real command output, beat by beat).
- **`vision/UUV_FLEET_ARCHITECTURE.md`** — **THE locked plan**: the 3-node topology (UUV Pis + fleet coordinator), the flywheel, the data-honesty fork.
- **`ONBOARDING.md`** — new teammate? get running + contributing in ~20 min.
- **`WARHACKER_HANDOFF.md`** — revive the AI copilot (WARHACKER) in a fresh session with full state.
- **`../ROADMAP.md`** — state, phases, and the update log (newest on top).

## Vision & plan
- **`vision/FLEET_LEARNING_VISION.md`** — the big vision (why fleet-learning is a category, not a tool).
- **`vision/BUILD_VISION.md`** — the build decision (council synthesis): what to build first, the moat, the honest framing.
- **`vision/PLAN.md`** — the shareable team plan (rallying narrative).
- **`TEAM_LANES.md`** — who owns what + the execute plan (run in your lane).

## Research
- **`research/DECK_BLUE_OCEAN.md`** — the market + why the lane is open (DECK opens the loop; THESEUS closes it).
- **`research/sbir/NAVSEA_SBIR_TOPICS.md`** — the demand signal: NV063 (the surface-contact / Framing-A track) + SOTA + SBIR mechanics.
- **`research/datasets/DATASETS.md`** — open datasets, ranked + license-cleared (and the honest proxy/UUV-data gap).
- **`research/council/COUNCIL_BRIEFS.md`** — the 4-lens design council (Architect / Visionary / Strategist / Red Team).

## Integration & compliance
- **`INTEGRATION_SPEC.md`** — buy/borrow/build: compose best-of-breed (in-toto/SLSA/cosign, OSCAL/Lula, Stone Soup, PyOD/River); build only the Navy-specific inch.
- **`DAY2_PREP.md`** — the red-team brief (the known weaknesses — read before any pitch/review).
- **`integration/DEFENSE_UNICORNS.md`** — THESEUS-on-UDS: inherit the ATO + the DU/Leidos delivery on-ramp.
- **`integration/INFERENCE_AND_FIPS.md`** — explainer engine (shore GPU + edge GGUF); FIPS = crypto boundary, not the model.
- **`compliance/IL_ROADMAP.md`** — unclass now → IL5 → IL6/Secret (inherit, don't rebuild).

## Setup / runbooks
- **`setup/MLFLOW_PODMAN.md`** — the Node-3 MLflow registry (Podman; offline/airgap staging).
- **`setup/PI_NODES.md`** — stand up the 2× Pi 5 (4 GB) as the UUV nodes (Node 1 / Node 2); DDIL beat; 4 GB gotchas.
- **`../KANBAN.md`** — the board.

## The rails (everywhere)
Human always in command — never autonomous · **all-real** (proxies + in-progress labeled) · tamper-**evident**, not tamper-proof · integrate-not-replace · **data honesty** (what the platform *watches* vs the platform's *own* UUV systems — kept separate) · **OPSEC** (no real names / commands in this public repo).
