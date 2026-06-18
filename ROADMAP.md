# THESEUS — Roadmap
*The master plan. Living doc — updated as we go (newest status on top). Tactical board: `KANBAN.md`. Lanes: `docs/TEAM_LANES.md`.*

**Mission:** onboard ship-systems analytics + edge model-delivery under DDIL — decision-support with human-in-command, on big surface combatants (DDG/CG). Real on real, **every model-promotion and human decision sealed as DoD-standard attestation evidence** (in-toto / SLSA / Sigstore + NIST **OSCAL** via Lula) — extended to *runtime, onboard*, the genuinely novel inch.

**Architecture — Jun 17 pivot (`docs/INTEGRATION_SPEC.md`):** compose best-of-breed open components that pass the **GATE** (permissive · airgap-capable · edge-feasible) — Stone Soup (fusion), Eclipse Zenoh + DDS plugin (DDIL transport *and* the SWAN-side ship-bus bridge), PyOD/Merlion/River (cold-start detection), MLflow + ONNX (lifecycle), UDS/Zarf/Pepr/Syft/cosign (deploy, already verified) — and **build only the ~15% non-commodity inch**: onboard cross-system fusion under DDIL · the **runtime-decision attestation extension** · the DDIL delivery loop · Navy domain knowledge. Adopting the standards *is* the moat-sharpener — a recognized, interoperable record is what makes other vendors emit *into* it. (Internal Merkle hash-chain stays as the implementation detail; the external artifact is standard attestations.)

## ★ North Star — the fleet-learning flywheel (the 10/10 vision · `docs/vision/FLEET_LEARNING_VISION.md`)
The founder's vision, and the apex this whole build climbs toward: **each ship is a self-contained city.** Every subsystem (machinery / power / propulsion / nav / damage-control / contacts) runs its own onboard ML + anomaly detection and **recommends to the watch — human always in command**, fully airgapped under DDIL. When the ship is **not in a contested environment**, it syncs **model deltas (never raw sensor data)** to a **fleet brain** (Blackwell / shore); the fleet improves as one — **Tesla-fleet-style, but human-authorized, eval-gated, and provenance-attested.**
- **The unification (why this scores 10):** the tamper-evident record is not a side feature — it is *what makes fleet learning accreditable*. It kills federated learning's two killers: **model-poisoning** (the fleet brain merges only provenance-attested deltas — reject a captured/compromised node's contribution) and **"you can't accredit a model that changes"** (you accredit the *pipeline's provenance*, not the frozen weights = **cATO-for-AI**, in the AO's own OSCAL language). The moat we already built and the biggest version of the mission are the **same artifact.**
- **We're not fighting the Navy's roadmap — we close it.** DECK / Project Overmatch *open* the loop (collect at the edge → ship ashore → retrain ashore); **THESEUS closes it** — learn *onboard* under DDIL + the safe, provenance-gated fleet-merge. THESEUS is the onboard payload the Warfighting Data Ecosystem (and UDS Fleet) surfaces.
- **Open lane — VERIFIED (Jun 17, sourced; `docs/research/DECK_BLUE_OCEAN.md`):** no named Navy AI-model **provenance/accreditation layer** exists today — DECK is a data pipeline (no model lineage), cATO is systems-level not model-level, and CDAO's AI-assessment framework isn't due until **~Jun 2027** → an **~18-month governance gap** where fleet learning ships with no accreditable record. *That gap is THESEUS's lane.* **Honest:** DECK's *internal* provenance isn't public and the integration isn't proven — claim the gap, not the integration. *(Acquisition/engagement is the founder's lane — handled.)*
- **Deliver now, demonstrate the vision:** ship the one-ship demo for the event, and **demonstrate the flywheel in miniature** — 2 simulated ships + a fleet brain (Mac + Blackwell, no physical-Pi dependency), each learns locally, "safe to sync," signed deltas, the fleet brain **merges only the attested ones (reject a poisoned delta live)**, eval-gate, push back, both improve, every step sealed. The whole vision on a table, disconnected. *(The fleet brain + real DECK integration is the longterm arc — Phase 3+.)*
- **Language discipline (carry into the room):** "*recommended* intervention, human-in-command" (never "the fleet updates itself"); "improves *safely* — every update eval-gated + attested + rollback-protected" (catastrophic forgetting is the real risk; those three are the answer).

## Hardware we have (real)
- **2× Raspberry Pi 5, 4GB** — Tier-2 nodes. **Pi-1 = MACHINERY** (CBM, 500GB SSD) · **Pi-2 = CONTACTS** (AIS PoL, 1TB SSD). On Tailscale (William). **Disk is ample → RAM (4GB) is the only constraint** (store big, but inference RAM-bound). Tommy has a container built on a Pi.
- **Gigabyte Ryzen, 32GB** — local on-prem **Tier-1** node (MLflow central server + heavier compute + retrain). The "ship data center" stand-in.
- **NVIDIA Blackwell cloud** — **Tier-1 GPU** (Triton-TRT-LLM explainer; the heaviest reasoning).
- 4GB/Pi ⇒ small models on the edge (CBM ✓, AIS PoL ✓, GGUF ≤~1.5B Q4). Heavy reasoning on Tier-1 (Ryzen/Blackwell). Architecture: `docs/architecture/COMPUTE_TIERS.md`.

## Status snapshot (Jun 17 — Day 1 close · judge re-score 6.9/10, was 5.4)
**The full system runs on real data, every step sealed + verified. Day 1 built the spine AND the depth:**
- **Model-delivery loop** — `demo/run.sh`: Stage→Retrain→Update on real UCI #316 (RMSE 0.0038), sealed.
- **AIS Pattern-of-Life (NV063)** — cold-start, explainable; **cross-region validated on Ushant** (the cold-start mechanism generalizes) → **cadence-aware `position_jump` fix** (Ushant false jumps 3151→771). Honest curated eval: **precision 0.57 · F1 0.70 · false-alarm 0.15** (was 0.36/0.53/0.39).
- **CIC dashboard** (`frontend/ui` :5173) — instrument-grade, **record-as-spine**, deck.gl tactical, **ACCEPT/OVERRIDE seals a `human_decision` leaf live** (`POST /api/decision`). 5th-pass rebuild after a 2026-design research sweep.
- **Real airgap UDS deploy** — uds-core/k3d + Theseus in-cluster Job (verify PASS) + **live Pepr admission** (4 violating pods DENIED — human-in-command enforced) + **Zarf SBOM (100 pkgs) + cosign**. `deploy/UDS_DEPLOY_EVIDENCE.md`.
- **Edge model-serving + shore→ship delivery** (`serve/`) — CPU/low-RAM server, sha-256 integrity gate, hot-swap-on-delivery sealed, last-good under bad updates (11/11 PASS).
- **ONNX edge inference** (`models/onnx/`) — CBM + autoencoder, parity 6e-08, ~115 KB, sub-ms (fits 4 GB Pi).
- **Shore→ship MLflow registry sync** (`deploy/mlflow-sync/`) — `mlflow-export-import` across the air-gap, ship serves verbatim (8/8 PASS). *(Juan's BDTS/CANES idea.)*
- **Offline ship hierarchy** (`serve/report_up.py` + `POST /api/node-report`) — edge nodes report up, brain aggregates live (honest TTL→standby); Pi deploy bundle ready (`deploy/pi/`).
- **Real Tier-1 explainer LLM** — `llama-server` + qwen2.5-1.5b serving grounded NV063 alerts, sealed (`explained_alert`).
- **Verified:** 21 tests green · DDIL cord-pull/rollback/tamper · whole-system end-to-end. **Team work merged.** OPSEC/integrity scrubbed.

---

## Phases

### Phase 0 — Foundation ✅ DONE
- [x] Public repo + organized docs (vision/research/setup/integration/compliance/architecture).
- [x] Model-delivery loop (`demo/`) — Stage→Retrain→Update, sealed, MLflow-optional, `--input` for ingest adapters.
- [x] AIS Pattern-of-Life cell (`demo/ais_pol.py`) — cold-start, explainable, real data (NV063 beat).
- [x] Tamper-evident record wired through every step; watchstander board (`show.py`).
- [x] Team lanes + 3 contracts; regression tests; IP-guard allowlist for the build tree.
- [x] Research: SBIR (NV063/NV061), datasets (catalog + 6 sets pulled), DU integration, inference/FIPS, IL roadmap.

### Phase 1 — Warhacker (Jun 17–19) 🔵 FINAL PUSH
*Event clock: **Day 1 (Jun 17)** build → **Day 2 (Jun 18)** final build day → **Day 3 (Jun 19)** present.*

**Day 1 (Jun 17) ✅ DONE — built the spine + the depth.** Judge re-score **6.9/10** (was 5.4). Everything in the Status snapshot above shipped, verified, and committed: two-tier architecture · the loop · AIS PoL + cross-region validation + cadence fix + honest eval · CIC dashboard + live decision-seal · **real UDS deploy** (Pepr admission + SBOM + cosign) · edge serve + shore→ship delivery · ONNX edge inference · MLflow shore→ship sync · ship hierarchy + Pi bundle · real explainer LLM · DDIL beat.

**🎯 Day 2 (Jun 18) — FINAL BUILD DAY, go hard → demo-ready.** Win condition: ONE all-real story — *stage→retrain→update across the 2 Pis + central MLflow → deployed on UDS → DDIL cord-pull → watch officer decides → every step sealed, shown live on the CIC* — plus the death-proof packet. **Per-person plan: `docs/TEAM_LANES.md` → Day 2.**
- [ ] **Light up the 2 Pis as live nodes** *(William; Pis hands-off until go)* — Pi-1 MACHINERY + Pi-2 CONTACTS reporting into the CIC hierarchy; multi-node DDIL failover over Tailscale. `deploy/pi/install.sh` is ready.
- [ ] **Central MLflow + analytics container** live, loop logs to it *(Tommy)*; Tailscale mesh + child-node serve *(Juan)*.
- [ ] **Death-proof packet** *(Carolina)* — Trivy/ZAP scan + the Zarf SBOM/cosign + a 1-page control-inheritance note.
- [ ] **Full uds-core** on a registry-mirrored host (dodge the GHCR throttle) → Istio mTLS + Keycloak + the Package CR reconciling (Portability 7→8.5). *(WARHACKER — stretch.)*
- [ ] **Pre-stage all images/models offline**; demo dry-run; 60s recorded fallback *(Aaron)*.
- [ ] **Attributed AO/PEO sentence** *(Joshua)* — the biggest Death-Proof unlock; relationship work, not code.
- [ ] **Pre-event-safe adopts** (`INTEGRATION_SPEC.md` §7 — low code risk, high score): have **Lula emit the record as NIST OSCAL** assessment-results + describe the sealed leaves as in-toto/SLSA-aligned (Death-Proof + Judges-Pick lift, mostly doc/format); wrap the autoencoder **inside PyOD** so the NV063 number is benchmarked vs 60 detectors, not bespoke. *(WARHACKER — fold into the hardening build.)*

**Day 3 (Jun 19) — PRESENT.** Run `docs/DEMO_SCRIPT.md` (5 beats, 3 min, all-real): the all-systems picture → cold-start anomaly → human decides (sealed) → DDIL cord-pull (serves last-good offline) → deploys on real UDS with live Pepr admission. Lead with the **record-as-accreditation** moat.

### Phase 2 — SBIR + team-week build-out (post-event → Jul 22)
- [ ] **NV063** (lead) Phase I — anomaly/PoL on real AIS, explainable, cold-start; OMTAD labeled eval + false-alarm number. *(WARHACKER + THESEUS)*
- [ ] **NV061** (companion) — TrAISformer trajectory baseline. *(THESEUS, `models/nv061/`)*
- [ ] Engage TPOCs in BZ03 pre-release (Q&A closes ~Jun 23); confirm SAM/SBC registrations + foreign-risk docs.
- [ ] Ingest adapters for all datasets → the loop (`ingest/`). *(THESEUS)*
- [ ] Live SDR cold-start (RTL-SDR on a Pi → real AIS/ADS-B). *(William + THESEUS plan)*
- [ ] **Buy/borrow/build heavy adopts** (`INTEGRATION_SPEC.md` §2/§7): **Stone Soup** cross-system fusion · **Eclipse Zenoh + DDS plugin** (SWAN-side ship-bus bridge + DDIL transport) · **automerge** CRDT ship-state · MLflow↔ONNX DDIL-loop hardening · **UDS Fleet** tenant registration (verify Fleet exposes per-node record ingestion — §5 open). Build only the 4-inch glue; everything else is borrowed.

### Phase 3 — Beachhead / pilot (6–18 mo)
- [ ] Host as a module on Fathom5 ERM v4 (back-door onto a hull); pursue a program-office sponsor (the real gate).
- [ ] UDS `iron-bank` flavor → ATO inheritance; Triton-TRT-LLM Tier-1 hardened; IL5→IL6 climb (`docs/compliance/IL_ROADMAP.md`).
- [ ] Add NV061 as 2nd tenant; turn the record into reusable ATO evidence; open the substrate to 3rd-party algorithms.

---

## Update log (newest on top)
- **Jun 17 (overnight) — BUY/BORROW/BUILD PIVOT (`docs/INTEGRATION_SPEC.md`, THESEUS lane).** Strategic reframe, founder-endorsed: stop re-deriving commodities; compose best-of-breed open components through the GATE (permissive · airgap · edge) and build only the ~15% non-commodity inch (onboard cross-system fusion under DDIL · runtime-decision attestation extension · DDIL delivery loop · Navy domain). **The moat reframe:** emit DoD-standard **in-toto/SLSA/Sigstore + NIST OSCAL (via Lula)** for *runtime* decisions, not a bespoke hash chain (Merkle chain → internal detail). Lifts Portability + Death-Proof (OSCAL = the AO's language) + Judges-Pick; cuts build surface ~80%. **Pre-event-safe (pull in now):** OSCAL/Lula emit from the record + PyOD benchmark wrap. **Phase 2 (heavy):** Stone Soup, Zenoh/DDS, automerge, UDS Fleet. Honest gates unchanged: standard ≠ AO acceptance (the sponsor sentence is still the kill-criterion); integration/packaging tax is real. *(Note: the overnight hardening workflow rate-limited out — re-running at lower concurrency when API capacity returns.)*
- **Jun 17 (late) — ROADMAP LOCKED for the final push; audit closed to 6.9/10.** Landed + verified + committed this session: real **UDS airgap deploy** (Zarf signed pkg + SBOM 100 pkgs + cosign + live Pepr admission, 4 DENY / 2 ADMIT); **edge model-serve + shore→ship delivery** (`serve/`, 11/11); **ONNX edge inference** (parity 6e-08, fits 4 GB Pi); **MLflow shore→ship sync** (Juan's `mlflow-export-import`, 8/8); **offline ship hierarchy** (edge→brain reporting + aggregation + Pi bundle, 7/7); **cross-region AIS validation** (Ushant — cold-start generalizes) → **cadence-aware `position_jump` fix** (3151→771); **honest NV063 re-eval** (precision 0.36→0.57, F1 0.70, far 0.15); **real Tier-1 explainer LLM** (`llama-server` + qwen2.5-1.5b, grounded alerts sealed). Folded team merges (analytics container, child-node compose, CodeQL scan). Pis hands-off per founder (bundle ready). **Timeline locked: Day 1 close → Day 2 (Jun 18) final build → Day 3 (Jun 19) present.**
- **Jun 17 (night)** — **Day 1 close: face now matches the substance.** (1) **CIC dashboard shipped** (`frontend/ui` :5173) — after 4 rejected "AI-slop" dashboards (glass+neon+Inter+grid), did a 4-angle 2026-design research sweep → rebuilt instrument-grade (amber-on-off-black, mono numerals, grain/hairlines, **record-as-spine**, deck.gl tactical, no glass/neon). Cleared the bar. (2) **Human-in-command made real** — `POST /api/decision` seals ACCEPT/OVERRIDE into the record (was theater; now verify PASS). (3) **Integrity/OPSEC scrub** — banned "self-controlled ship brain" headline gone from all public surfaces; named NIWC official + OCI/"rides onto a ship" overclaim removed; surnames out of the public repo; roster corrected to the real 9 (Joshua=Lead). (4) **Team work merged** — analytics container (Tommy), child-node compose (Juan, WIP), anomaly-explaining train.py (Nick). (5) **Whole system verified end-to-end** (21 tests + DDIL + eval + API/seal). (6) **Real UDS deploy launched** (uds-core/k3d + Theseus Job + Pepr admission + SBOM/cosign). Day 2 = per-person execute plan in TEAM_LANES.
- **Jun 17 (eve+)** — **Explainable-alert layer** (`demo/explainer.py`, NV063): deterministic detection → local LLM (qwen2.5:1.5b = team's Pi model; verified real grounded alerts via qwen3.6) → watch alert + action, sealed; template fallback. **+ autoencoder** (ROC-AUC 0.978). **THESEUS track delivered**: NV063 technical approach, MODEL_BENCHMARKS, eval results, NV061 fuller run. Team KANBAN: Pi models = Qwen2.5-1.5B / Gemma-3-1B via llama.cpp; Juan MLflow compose; Carolina ZAP scan. Repo-hygiene catch: `data/` gitignore lost in a merge (2.2GB at risk) — fixed, never committed (.git=2.8M). Demo machine = this Mac; ports moved off 5000 (AirPlay).
- **Jun 17 (eve)** — **Stack live on this machine + Pi-1.** Tier-1 **MLflow** running (containerized on :5001 — host py3.14 server is broken by an `importlib.abc.Traversable` removal, which *validates* containerizing it). **Trained 3 real datasets through MLflow**: theseus-gt_compressor_decay (RMSE 0.0038), theseus-rul (41.3 cyc), theseus-is_anomaly (0.042). **Pi-1 = machinery node**: the CBM loop runs **containerized via podman 5.4.2** on real data (RMSE 0.0059, record PASS), stdlib-only (no deps). Merged Juan's `deploy/mlflow-compose/`. SSH (key) to both Pis working. Frontend (impressive Streamlit) building.
- **Jun 17 (pm)** — Hardware detail: pi1 500GB SSD / pi2 1TB SSD → **disk ample, RAM (4GB) is the only constraint**. Tommy built a container on a Pi (arm64 path works). GitHub repo access being granted to the team (per-repo collaborators on `theseus` only — founder action).
- **Jun 17 (pm)** — **Frontend data contract shipped** (`demo/api.py` → `/api/state`, JSON, CORS) so Gerardo (Frontend) + Aaron (Data+Frontend) build the UI against the sealed record. Roles updated from team self-report: Carolina=IL6+SW versions, Thang=Pi Dockerfile, Josh=scaffolding, Nick=train-on-JSON+MLflow, William=Pis/Tailscale, Gerardo=Frontend, Aaron=Data+Frontend.
- **Jun 17 (pm)** — **`deploy/` tree landed + verified:** Containerfile builds + runs hardened (real data, verify PASS), DDIL beat runs, Pepr policy compiles, YAML valid. Added **Gigabyte Ryzen 32GB** as local Tier-1. **Team active:** Carolina=IL6 baseline+SW versions, Thang=Pi analytics Dockerfile, William=Pis+Tailscale, Juan=Tailscale integration, Nick=MLflow. *(SSH to the Pis/Ryzen: I can't authenticate with passwords — see chat; key-based or team-run.)*
- **Jun 17** — Hardware confirmed: **2× Pi 5 4GB** (Tier-2, 2 organs) + Blackwell (Tier-1). Master roadmap created. Watchstander board + two-tier architecture + vLLM/FIPS verdict shipped. UDS packaging workflow landing.
- **Jun 17** — Demo is a runnable 3-step story (loop + AIS PoL + board) on real data; THESEUS lanes assigned; datasets pulled.
