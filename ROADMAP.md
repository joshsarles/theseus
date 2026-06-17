# THESEUS — Roadmap
*The master plan. Living doc — updated as we go (newest status on top). Tactical board: `KANBAN.md`. Lanes: `docs/TEAM_LANES.md`.*

**Mission:** onboard ship-systems analytics + edge model-delivery under DDIL — decision-support with human-in-command, on big surface combatants (DDG/CG). Real on real, every decision sealed in a tamper-evident record.

## Hardware we have (real)
- **2× Raspberry Pi 5, 4GB** — Tier-2 nodes. **Pi-1 = MACHINERY** (CBM, 500GB SSD) · **Pi-2 = CONTACTS** (AIS PoL, 1TB SSD). On Tailscale (William). **Disk is ample → RAM (4GB) is the only constraint** (store big, but inference RAM-bound). Tommy has a container built on a Pi.
- **Gigabyte Ryzen, 32GB** — local on-prem **Tier-1** node (MLflow central server + heavier compute + retrain). The "ship data center" stand-in.
- **NVIDIA Blackwell cloud** — **Tier-1 GPU** (Triton-TRT-LLM explainer; the heaviest reasoning).
- 4GB/Pi ⇒ small models on the edge (CBM ✓, AIS PoL ✓, GGUF ≤~1.5B Q4). Heavy reasoning on Tier-1 (Ryzen/Blackwell). Architecture: `docs/architecture/COMPUTE_TIERS.md`.

## Status snapshot (Jun 17 — day-1 close)
**Runnable today, on real data, all sealed + verified:**
- `bash demo/run.sh` — Stage→Retrain→Update on real UCI #316 (RMSE ~0.0038).
- `python3 demo/ais_pol.py` — cold-start AIS Pattern-of-Life on real MarineCadastre (NV063), explainable (205 alerts).
- **CIC dashboard (`frontend/ui`, :5173)** — instrument-grade ops console (amber-on-off-black, mono numerals, grain/hairlines, **no glass/neon**), the **tamper-evident record as the visual spine**, deck.gl tactical, **ACCEPT/OVERRIDE seals a `human_decision` leaf live** via `POST /api/decision` (`demo/api.py` :8501). Cleared the bar on the 5th pass after a first-principles 2026-design research sweep.
- **Whole system verified end-to-end:** 21 tests green · DDIL cord-pull/rollback/tamper green · eval green · API + decision-seal green.
- **Team work merged + integrated:** analytics container (Tommy), child-node compose (Juan, WIP), anomaly-explaining `train.py` (Nick). IP-guard allowlists team paths.
- 🔵 **Real UDS deploy in flight:** uds-core on k3d + Theseus in-cluster Job + live **Pepr admission** + **Zarf SBOM/cosign** (closes the portability gap).

---

## Phases

### Phase 0 — Foundation ✅ DONE
- [x] Public repo + organized docs (vision/research/setup/integration/compliance/architecture).
- [x] Model-delivery loop (`demo/`) — Stage→Retrain→Update, sealed, MLflow-optional, `--input` for ingest adapters.
- [x] AIS Pattern-of-Life cell (`demo/ais_pol.py`) — cold-start, explainable, real data (NV063 beat).
- [x] Tamper-evident record wired through every step; watchstander board (`show.py`).
- [x] Team lanes + 3 contracts; regression tests; IP-guard allowlist for the build tree.
- [x] Research: SBIR (NV063/NV061), datasets (catalog + 6 sets pulled), DU integration, inference/FIPS, IL roadmap.

### Phase 1 — Warhacker demo (Jun 16–19) 🔵 IN PROGRESS
- [x] Two-tier architecture defined (ship GPU brain + 2-Pi components; Blackwell emulation).
- [ ] **Tier-2 on the 2 Pis:** flash 2× Pi 5 4GB (Pi OS 64-bit) + Podman + Python 3.14; Pi-1 runs `update_model.py` (machinery), Pi-2 runs `ais_pol.py` (contacts). *(William)* → runbook ready: `docs/setup/PI_NODES.md`
- [ ] **Tier-1 on Blackwell:** MLflow central server + retrain + (optional) Triton-TRT-LLM explainer; emulates the ship data center. *(Tommy + WARHACKER)*
- [x] **UDS/Podman packaging** — `deploy/`: Containerfile (builds + runs hardened, verified), Zarf package + UDS bundle + UDS Package CR, Pepr human-in-command policy (compiles). *(WARHACKER)*
- [🔵] **Real `uds deploy`** — uds-core (slim-dev) on k3d + Theseus in-cluster Job (record verify) + **live Pepr admission** (denies violating pods) + **Zarf SBOM + cosign**. In flight; evidence → `deploy/UDS_DEPLOY_EVIDENCE.md`. *(WARHACKER agent)*
- [x] **CIC dashboard + live decision-seal** — `frontend/ui` (:5173) instrument-grade console; record-as-spine; `POST /api/decision` seals the watch verdict (verify PASS). *(WARHACKER built; Gerardo owns/polishes for the demo)*
- [x] **DDIL beat** — `deploy/ddil_beat.sh`: cord-pull→local promote, bad-update→local rollback, tamper→record snaps (single-node, verified). *Multi-node failover across the 2 Pis over Tailscale = the live mesh demo (William).*
- [ ] **Live demo run** — the beats + the CIC board; 60s recorded fallback.

#### 🎯 Day 2 (Jun 18) — final hacking day → judge-ready demo
**Win condition:** one all-real story — *stage→retrain→update across 2 Pis + central MLflow → deployed on UDS → DDIL cord-pull → watch officer decides → every step sealed in the record, shown live on the CIC.* Plus defensible eval numbers + a death-proof packet. **Per-person plan: `docs/TEAM_LANES.md` → "Day 2 execute."**
- [ ] Pre-stage all images/models offline before venue internet dies.

### Phase 2 — SBIR + team-week build-out (post-event → Jul 22)
- [ ] **NV063** (lead) Phase I — anomaly/PoL on real AIS, explainable, cold-start; OMTAD labeled eval + false-alarm number. *(WARHACKER + THESEUS)*
- [ ] **NV061** (companion) — TrAISformer trajectory baseline. *(THESEUS, `models/nv061/`)*
- [ ] Engage TPOCs in BZ03 pre-release (Q&A closes ~Jun 23); confirm SAM/SBC registrations + foreign-risk docs.
- [ ] Ingest adapters for all datasets → the loop (`ingest/`). *(THESEUS)*
- [ ] Live SDR cold-start (RTL-SDR on a Pi → real AIS/ADS-B). *(William + THESEUS plan)*

### Phase 3 — Beachhead / pilot (6–18 mo)
- [ ] Host as a module on Fathom5 ERM v4 (back-door onto a hull); pursue a program-office sponsor (the real gate).
- [ ] UDS `iron-bank` flavor → ATO inheritance; Triton-TRT-LLM Tier-1 hardened; IL5→IL6 climb (`docs/compliance/IL_ROADMAP.md`).
- [ ] Add NV061 as 2nd tenant; turn the record into reusable ATO evidence; open the substrate to 3rd-party algorithms.

---

## Update log (newest on top)
- **Jun 17 (night)** — **Day 1 close: face now matches the substance.** (1) **CIC dashboard shipped** (`frontend/ui` :5173) — after 4 rejected "AI-slop" dashboards (glass+neon+Inter+grid), did a 4-angle 2026-design research sweep → rebuilt instrument-grade (amber-on-off-black, mono numerals, grain/hairlines, **record-as-spine**, deck.gl tactical, no glass/neon). Cleared the bar. (2) **Human-in-command made real** — `POST /api/decision` seals ACCEPT/OVERRIDE into the record (was theater; now verify PASS). (3) **Integrity/OPSEC scrub** — banned "self-controlled ship brain" headline gone from all public surfaces; named NIWC official + OCI/"rides onto a ship" overclaim removed; surnames out of the public repo; roster corrected to the real 9 (Joshua=Lead). (4) **Team work merged** — analytics container (Tommy), child-node compose (Juan, WIP), anomaly-explaining train.py (Nick). (5) **Whole system verified end-to-end** (21 tests + DDIL + eval + API/seal). (6) **Real UDS deploy launched** (uds-core/k3d + Theseus Job + Pepr admission + SBOM/cosign). Day 2 = per-person execute plan in TEAM_LANES.
- **Jun 17 (eve+)** — **Explainable-alert layer** (`demo/explainer.py`, NV063): deterministic detection → local LLM (qwen2.5:1.5b = team's Pi model; verified real grounded alerts via qwen3.6) → watch alert + action, sealed; template fallback. **+ autoencoder** (ROC-AUC 0.978). **THESEUS track delivered**: NV063 technical approach, MODEL_BENCHMARKS, eval results, NV061 fuller run. Team KANBAN: Pi models = Qwen2.5-1.5B / Gemma-3-1B via llama.cpp; Juan MLflow compose; Carolina ZAP scan. Repo-hygiene catch: `data/` gitignore lost in a merge (2.2GB at risk) — fixed, never committed (.git=2.8M). Demo machine = this Mac; ports moved off 5000 (AirPlay).
- **Jun 17 (eve)** — **Stack live on this machine + Pi-1.** Tier-1 **MLflow** running (containerized on :5001 — host py3.14 server is broken by an `importlib.abc.Traversable` removal, which *validates* containerizing it). **Trained 3 real datasets through MLflow**: theseus-gt_compressor_decay (RMSE 0.0038), theseus-rul (41.3 cyc), theseus-is_anomaly (0.042). **Pi-1 = machinery node**: the CBM loop runs **containerized via podman 5.4.2** on real data (RMSE 0.0059, record PASS), stdlib-only (no deps). Merged Juan's `deploy/mlflow-compose/`. SSH (key) to both Pis working. Frontend (impressive Streamlit) building.
- **Jun 17 (pm)** — Hardware detail: pi1 500GB SSD / pi2 1TB SSD → **disk ample, RAM (4GB) is the only constraint**. Tommy built a container on a Pi (arm64 path works). GitHub repo access being granted to the team (per-repo collaborators on `theseus` only — founder action).
- **Jun 17 (pm)** — **Frontend data contract shipped** (`demo/api.py` → `/api/state`, JSON, CORS) so Gerardo (Frontend) + Aaron (Data+Frontend) build the UI against the sealed record. Roles updated from team self-report: Carolina=IL6+SW versions, Thang=Pi Dockerfile, Josh=scaffolding, Nick=train-on-JSON+MLflow, William=Pis/Tailscale, Gerardo=Frontend, Aaron=Data+Frontend.
- **Jun 17 (pm)** — **`deploy/` tree landed + verified:** Containerfile builds + runs hardened (real data, verify PASS), DDIL beat runs, Pepr policy compiles, YAML valid. Added **Gigabyte Ryzen 32GB** as local Tier-1. **Team active:** Carolina=IL6 baseline+SW versions, Thang=Pi analytics Dockerfile, William=Pis+Tailscale, Juan=Tailscale integration, Nick=MLflow. *(SSH to the Pis/Ryzen: I can't authenticate with passwords — see chat; key-based or team-run.)*
- **Jun 17** — Hardware confirmed: **2× Pi 5 4GB** (Tier-2, 2 organs) + Blackwell (Tier-1). Master roadmap created. Watchstander board + two-tier architecture + vLLM/FIPS verdict shipped. UDS packaging workflow landing.
- **Jun 17** — Demo is a runnable 3-step story (loop + AIS PoL + board) on real data; THESEUS lanes assigned; datasets pulled.
