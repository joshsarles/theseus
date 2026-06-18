# THESEUS — Team Lanes & Execute Plan
*So everyone runs in their own lane without colliding, and we ship something real today + tomorrow. Owner of this doc: WARHACKER (orchestration). Update freely.*

## The shared spine everyone plugs into (already runs: `bash demo/run.sh`)
`Stage Operational Data → Retrain → Update local model`, every step sealed in the tamper-evident record. Three contracts hold the lanes together:
1. **Data contract** — `demo/data/staged.csv` (target = last column). *(Owner: data lane / SDR)*
2. **Model contract** — MLflow registry `theseus-cbm/v{N}`. *(Owner: build lane)*
3. **Record contract** — `_record.seal(out_dir, kind, obs_id, dict)`; every lane seals its step. *(Owner: WARHACKER)*

## Lanes — who owns what, and the interface they expose
| Lane | Owner | Owns | Interface to the rest | Don't touch |
|---|---|---|---|---|
| **Edge / Pi cluster** | **William** | Flash Pis (Pi OS 64-bit), network them, Podman + Python 3.14, **SDR rig** (RTL-SDR + AIS-catcher + dump1090-fa = live AIS/ADS-B cold-start) | Runs `demo/update_model.py` on the Pi; registers to MLflow `:5000`; receives the UDS bundle | the MLflow server config, datasets/ |
| **Build / MLOps** | **Tommy** | MLflow central server in Podman (`docs/setup/MLFLOW_PODMAN.md`), the train/register/version flow | `MLFLOW_TRACKING_URI`; `retrain.py` logs to it; registry `theseus-cbm` | the Pi provisioning, the record internals |
| **MLOps config / PM** | **Carolina + Juan** | KanBan, version pins (MLflow 3.13 / Podman >5.8.1 / Python 3.14.4), container architecture, CVE hygiene | keeps board + versions current | model code, edge HW |
| **Data / research** | **THESEUS agent** | `docs/research/datasets/` (catalog + A–F + ROADMAP), license clearing, SDR capture plan, NV061 trajectory data | the **data contract** (CSV shape stage_data expects) | demo/ code, deploy/ |
| **Orchestration / trust** | **WARHACKER** | the demo scaffold (`demo/`), the **record/trust layer** (the moat), **DU/UDS integration**, SBIR + strategy framing, compliance, repo coherence + push cadence | the record contract; the lanes doc; the build plan; folds in everyone's pushes | others' in-flight files (pull before push) |

## Team roster (10)
| Member | Lane |
|---|---|
| **Joshua** — Team Lead | direction · system scaffolding |
| **William** | Edge / Pi cluster + SDR rig + Tailscale |
| **Carolina** | Security — IL6 baseline + SW versions (ZAP scan) |
| **Tommy** | Build / MLOps — analytics container + MLflow pipeline |
| **Savannah** | open — eval / labeling |
| **Gerardo** | Frontend |
| **Nicholas** | Models — training + MLflow |
| **Juan** | Networking / MLOps — Tailscale + MLflow container |
| **Aaron** | Data + Frontend |
| **Mark** | Strategy / engagement (Force; retired Marine) |
| **Claire** | Models — trains the UUV own-systems model on Node 3 (NAVSEA intern) |

*Team = 11: NAVSEA (incl. intern) + retired Navy/Marine engineers + analysts (no NIWC). Surnames kept out of this public repo (OPSEC); accurate roster lives in the team channel. The NIWC official referenced in an earlier draft is NOT on the team — scrubbed. Force AI agents (not team members): WARHACKER = orchestration/build/record/DU · THESEUS = data/research/eval.*

## Collision rules (we share one repo)
- **Pull before you push** (`git pull --no-edit origin main` then push). **Push often.**
- Work in **your lane's files/dirs**; if you must touch a shared file, say so on the board.
- Generated artifacts are gitignored (`demo/out|registry|models`); real pre-staged data (`demo/data/staged.csv`) is committed.

## 🎯 DAY 2 (Jun 18) — final hacking day → judge-ready demo
**Win condition:** ONE all-real story — *stage→retrain→update across the 2 Pis + central MLflow → deployed on UDS → DDIL cord-pull → watch officer decides → every step sealed in the record, shown live on the CIC dashboard* — plus defensible eval numbers + a death-proof packet.

**Already done (day 1):** the CIC dashboard (`frontend/ui` :5173, record-as-spine, live decision-seal), the single-node loop + DDIL beat + AIS PoL, whole-system verify (21 tests), team work merged, real UDS deploy in flight (WARHACKER agent).

Everyone owns ONE deliverable, to their strength:

| Owner | Strength | Day-2 deliverable | Done = |
|---|---|---|---|
| **William** | Edge / Pi + SDR + Tailscale | Both Pis live as Tier-2 (Pi-1 MACHINERY / Pi-2 CONTACTS) + **multi-node DDIL failover** over Tailscale; live RTL-SDR AIS cold-start on Pi-2 if the rig's ready | cord-pull a Pi → the other serves last-good → reconnect → bundle update; record PASS |
| **Tommy** | Build / MLOps | **Central MLflow** up (containerized, pre-staged offline) + the **analytics container** deployed; `retrain.py` logs to it (registry `theseus-cbm`) | a real run + registered model in central MLflow, no internet |
| **Juan** | Networking / MLOps | Tailscale mesh (Mac Tier-1 + 2 Pis) solid; **fix the child-node compose** (correct model server/model/MLflow, drop GPU) → the **edge model-serve + shore→ship push** path | a model pushed shore→Pi via the compose/bundle, served on the Pi |
| **Nicholas** | Models | Finalize the **anomaly-explaining** model (`train.py`) logging to MLflow; CBM + autoencoder + anomaly all registered + loop-deployable | the showcase anomaly model runs with explanations, on MLflow |
| **Carolina** | Security / IL6 | The **death-proof packet**: Trivy/ZAP scan of the deployed stack + the **Zarf SBOM + cosign** (from the UDS deploy) + a 1-page **control-inheritance** note (UDS 800-53 baseline + the Theseus delta) | a judge-ready security/compliance artifact in `docs/compliance/` |
| **Savannah** | Eval / labeling | An **analyst-curated AIS eval set** (OMTAD-style) → an honest NV063 number through `eval/score.py` | a defensible precision/recall/false-alarm, not self-graded |
| **Gerardo** | Frontend | **Own + run the CIC dashboard** for the demo: point at the live API, verify the ACCEPT/OVERRIDE→seal climax, polish + drive the screen | dashboard demo-ready; he runs the live flow |
| **Aaron** | Data + Frontend | **Demo data prep**: clean/representative AIS + CBM slices; the live-SDR fallback dataset; support Gerardo | the demo runs on clean, defensible data + a recorded fallback |
| **Joshua** | Lead | The **judge narrative** + the **sponsor/AO line** (an attributed program-office sentence — the death-proof "sponsor" gap); final dry-run direction | the 3-minute story + who-buys-this is crisp |

**Agents:** **WARHACKER** = orchestration · the real UDS deploy · death-proof packet assembly · demo script · repo coherence (fold in pushes). **THESEUS** = data/research/eval support (NV063 eval, ingest adapters).

## Principles we can borrow (IP stays private — never vendored into this public repo)
Per founder: draw *principles* from Force OS / force-core, `Projects/Metropolis`, `Developer/Projects/Research` — not the IP. Same discipline as the record's production ledger: crown-jewel implementations ride as **private deps / wheels / containers**, only the clean interface lives here.
- **Force OS / force-core:** agent orchestration + the airgap deploy/runtime pattern → how the Pi nodes are coordinated and re-fielded.
- **Metropolis:** fusion / corpus-harvesting patterns → how heterogeneous feeds normalize into one picture.
- **Research (PULSE etc.):** consensus / monitoring patterns → multi-node agreement + drift watch on the edge.
- **Rule:** if a principle helps, implement a clean-room version behind the public interface; do not copy private source into `theseus`.
