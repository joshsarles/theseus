# THESEUS — Roadmap
*The master plan. Living doc — updated as we go (newest status on top). Tactical board: `KANBAN.md`. Lanes: `docs/TEAM_LANES.md`.*

**Mission:** the self-controlled ship brain — onboard analytics + edge model-delivery under DDIL, decision-support with human-in-command, on big surface combatants (DDG/CG). Real on real, every decision sealed in a tamper-evident record.

## Hardware we have (real)
- **2× Raspberry Pi 5, 4GB** — the Tier-2 system-component nodes. Maps cleanly to **2 organs**: **Pi-1 = MACHINERY** (CBM gas-turbine model) · **Pi-2 = CONTACTS** (AIS Pattern-of-Life).
- **NVIDIA Blackwell cloud** — emulates the ship's **Tier-1** central GPU compute (fusion + explainer + onboard retrain + MLflow).
- 4GB/Pi ⇒ small models only on the edge: the CBM model is tiny ✓, AIS PoL is light Python ✓, GGUF ≤~1.5B Q4 if an edge LLM is needed. Heavy reasoning lives on Tier-1 (Blackwell). Architecture: `docs/architecture/COMPUTE_TIERS.md`.

## Status snapshot (Jun 17)
**Runnable today, on real data, all sealed + verified:**
- `bash demo/run.sh` — Stage→Retrain→Update on real UCI #316 (RMSE ~0.0038).
- `python3 demo/ais_pol.py` — cold-start AIS Pattern-of-Life on real MarineCadastre (NV063), explainable.
- `python3 demo/show.py` — the watchstander board (recommend→human-decides, record PASS).
- Regression tests green; IP-guard fixed; docs organized + pushed.

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
- [ ] **Tier-2 on the 2 Pis:** flash 2× Pi 5 4GB (Pi OS 64-bit) + Podman + Python 3.14; Pi-1 runs `update_model.py` (machinery), Pi-2 runs `ais_pol.py` (contacts). *(William)*
- [ ] **Tier-1 on Blackwell:** MLflow central server + retrain + (optional) Triton-TRT-LLM explainer; emulates the ship data center. *(Tommy + WARHACKER)*
- [ ] **UDS/Podman packaging** — Containerfile + Zarf package + UDS bundle + Pepr human-in-command policy. *(WARHACKER — in flight)*
- [ ] **DDIL beat** — cut shore: both Pis keep serving last-good, record holds, rollback works. *(WARHACKER)*
- [ ] **Live demo run** — the 4 beats + the watchstander board; 60s recorded fallback.
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
- **Jun 17** — Hardware confirmed: **2× Pi 5 4GB** (Tier-2, 2 organs) + Blackwell (Tier-1). Master roadmap created. Watchstander board + two-tier architecture + vLLM/FIPS verdict shipped. UDS packaging workflow landing.
- **Jun 17** — Demo is a runnable 3-step story (loop + AIS PoL + board) on real data; THESEUS lanes assigned; datasets pulled.
