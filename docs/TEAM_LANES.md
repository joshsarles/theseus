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

## Team roster (9)
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

*Surnames kept out of this public repo (OPSEC); accurate roster lives in the team channel. The NIWC official referenced in an earlier draft is NOT on the team — scrubbed. Force AI agents (not team members): WARHACKER = orchestration/build/record/DU · THESEUS = data/research/eval.*

## Collision rules (we share one repo)
- **Pull before you push** (`git pull --no-edit origin main` then push). **Push often.**
- Work in **your lane's files/dirs**; if you must touch a shared file, say so on the board.
- Generated artifacts are gitignored (`demo/out|registry|models`); real pre-staged data (`demo/data/staged.csv`) is committed.

## TODAY (Day 0) — get everyone green
- [ ] **Everyone:** clone, `bash demo/run.sh` → see the loop green on **real UCI #316** (RMSE ~0.0038, record verify PASS).
- [ ] **Tommy:** MLflow server up in Podman; `export MLFLOW_TRACKING_URI=http://<ip>:5000`; `pip install scikit-learn`; `python3 demo/retrain.py` logs a run + artifact.
- [ ] **William:** 1 Pi flashed (Pi OS 64-bit) + Podman + Python 3.14; run `demo/update_model.py` on the Pi; order/assemble the RTL-SDR.
- [ ] **THESEUS agent:** clear the 5 license items; hand William the SDR capture plan; pull Tier-1 AIS sets (MarineCadastre/Ushant).
- [ ] **WARHACKER:** UDS bundle scaffold (zarf/uds/Pepr) so the loop ships as a UDS package; IL compliance note.

## TOMORROW (Day 1) — the demo end-to-end
- [ ] Full chain across ≥2 Pis: stage (real / live SDR) → retrain on the **central MLflow** → push model to the Pi → `update_model.py` promotes + seals → verify PASS.
- [ ] Add the **AIS Pattern-of-Life anomaly** model as a 2nd model on the same loop (the NV063 beat).
- [ ] **DDIL beat:** pull the network cord → Pi keeps serving last-good → record holds → `models/previous` rollback works.
- [ ] Package as a **UDS/Zarf airgap bundle**; pre-stage all images + models.
- [ ] Demo dry-run + the narration: *"stage → retrain → update, every step provable, runs disconnected."*

## Principles we can borrow (IP stays private — never vendored into this public repo)
Per founder: draw *principles* from Force OS / force-core, `Projects/Metropolis`, `Developer/Projects/Research` — not the IP. Same discipline as the record's production ledger: crown-jewel implementations ride as **private deps / wheels / containers**, only the clean interface lives here.
- **Force OS / force-core:** agent orchestration + the airgap deploy/runtime pattern → how the Pi nodes are coordinated and re-fielded.
- **Metropolis:** fusion / corpus-harvesting patterns → how heterogeneous feeds normalize into one picture.
- **Research (PULSE etc.):** consensus / monitoring patterns → multi-node agreement + drift watch on the edge.
- **Rule:** if a principle helps, implement a clean-room version behind the public interface; do not copy private source into `theseus`.
