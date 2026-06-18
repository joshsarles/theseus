# THESEUS — UUV Fleet-Learning Architecture (the locked plan)

*Web-grounded Jun 18 2026 (PAE RAS/DECK + Tesla-FSD research). Companion to `FLEET_LEARNING_VISION.md` (the why), `INTEGRATION_SPEC.md` (buy/borrow/build), `ROADMAP.md` (state). This is the *what we're building and how we frame it.*

> **One line:** THESEUS is **"Tesla FSD for a fleet of unmanned maritime vehicles — DDIL-native and accreditable."** Each vehicle learns locally under denied comms; a **fleet node** coordinates model deltas (never raw data) with a provenance-gated, eval-gated, signed merge; the fleet improves safely. It is the **fleet model-coordination + trust layer that does not exist yet** above the platforms.

---

## §1 — The three layers

**Node topology (locked, prototype scale):**
- **Node 1 = UUV 1** · **Node 2 = UUV 2** — Raspberry Pi 5 (4 GB) onboard brains.
- **Node 3 = this machine (the Mac)** — **fleet coordination**: hosts **MLflow** (Juan's `deploy/mlflow-compose/` — Postgres + MLflow server) + the **UI**, and **manages the Pis**. It aggregates the improvements from Nodes 1+2, picks the best (eval-gate), and pushes the improved model back down to 1+2.
- **No Node 4** for the prototype — the explainer/command-center role folds into Node 3 at this scale (it's the natural "shore/fleet-brain" expansion node later). *(The same topology scales: Node 3 can be a ship-brain with the UUVs as subsystems, or a fleet-brain with more vehicles — the model is N-node.)*

1. **UUV brains = the 2 Raspberry Pis (Nodes 1 + 2).** Each Pi is one unmanned vehicle's onboard brain. Submerged = **hard DDIL** (Denied/Degraded/Intermittent/Limited-bandwidth — the DoD-standard meaning). It runs **lightweight models locally** (machinery health, anomaly/contact detection) doing real-time onboard analytics + decisions with zero connectivity. The onboard anomaly models double as Tesla-style **"trigger classifiers"** — only *flagged/interesting* deltas surface, never raw sensor data.
2. **The fleet node = the coordinator.** A central node (Mac/Ryzen now; an afloat/relay/shore coordinator in reality) running **MLflow as the model registry + the fleet brain**. It **pushes models down** to the vehicles and **pulls signed model deltas up** when a vehicle surfaces (an opportunistic comms window), then **coordinates the merge**.
3. **The loop = the flywheel.** Learn local (DDIL) → surface → push signed deltas → fleet node **merges (provenance-gated) + eval-gates + registers** → pushes the improved model back down → the whole fleet gets smarter. Tesla's loop, adapted for DDIL via **federated learning** (deltas, not raw data) with a **Byzantine-robust / provenance-gated** merge and a **pre-deployment eval-gate** (you cannot recall a bad model from a submerged vehicle).

---

## §2 — How it maps to the Navy reality (research-corrected)

- **PAE RAS** (Portfolio Acquisition Executive for Robotic & Autonomous Systems, est. Sep 2025; ~50–66 unmanned programs; ~$19B/5yr; SD Industry Day Jun 10–11 2026) is the **acquisition/integration authority for unmanned** — it funds *platforms* (REMUS, Orca XLUUV, Snakehead, USVs), **not** AI/ML. So the "learn + coordinate" layer sits **inside/above the platforms**, sold via the PAE RAS **OTA Marketplace Roadmap** (accelerated, <12-mo prototype→production) or the **platform integrators** (HII, GD, Boeing), not to PAE RAS leadership directly.
- **DECK** (Applied Intuition, delivered Mar 2026, in the PAE RAS portfolio) = **ship-based** data pipelines + OTA pushes + bandwidth optimization. **It does NOT do:** onboard closed-loop learning under DDIL, **fleet model coordination (no registry / no fleet brain)**, or UUV-specific subsea learning. **⚠ Correction: do NOT claim "we plug into DECK"** — DECK is manned-ship-centric; the honest line is the **post-DECK forward problem**: *"DECK collects ship data; the missing piece is coordinating learning across a fleet of edge-autonomous vehicles, with a record an AO can accredit."*
- **Compatible-with, not competing:** **HII Odyssey ACS** (autonomy/tasking on 750+ REMUS, 35+ USVs) does *mission tasking + trajectory planning*; **Project Overmatch** does *C2 + data routing*. Neither does **ML model management/versioning across the fleet** — that's our layer. Position THESEUS as the **fleet-MLOps + trust layer** that rides *on* Odyssey/Overmatch.
- **The open lane (verified):** there is **no named Navy program** for a fleet model registry / fleet-brain coordinating ML across unmanned vehicles, and **no model-provenance/accreditation layer** for AI that changes (CDAO's AI-assessment framework not due until ~Jun 2027). The infrastructure exists (Overmatch, Odyssey, mesh nets); the **ML-coordination + accreditation layer does not.**

---

## §3 — The Tesla FSD adaptation (steal the loop, concede the disanalogies)

**Steal:** trigger-based **selective upload** (only flagged data), central retrain + **versioning**, validated **OTA push + rollback**, the iterative flywheel.

**Adapt (this is the credibility):**
| Tesla | UUV fleet (what we do) |
|---|---|
| Always-connected, 5M cars | **DDIL**, 10–50 vehicles → round-based sync on surface |
| Upload raw clips, train centrally | **Federated learning: upload signed *deltas*, not raw sonar** (bandwidth + classification) |
| Regressions caught in the field across millions | **No field signal / no recall to a submerged vehicle → eval-gate must be airtight PRE-deployment** |
| No adversary | **Captured-UUV poisoning is the threat → provenance-gated / Byzantine-robust merge** (our poison-rejection beat) |

**Say:** *"We adopt Tesla's proven fleet-learning loop, adapted for UUVs via federated learning + Byzantine-robust aggregation + pre-deployment validation."* **Don't say:** "Tesla for the Navy" / "real-time regression detection" / "raw data on-device uploaded." Naming the disanalogies out loud is what an informed judge respects.

---

## §4 — Models + the data-honesty fork (read this carefully)

Two framings are easy to tangle; keep them **separate and honestly labeled** (an SME will catch a slip):

| Framing | What it is | Right data today? |
|---|---|---|
| **A — what the platform WATCHES** (NV063, the funded SBIR) | Pattern-of-Life anomaly of surface+air **contacts** around the platform (AIS+ADS-B+radar → SSDS) | **YES** — AIS (MarineCadastre/Ushant/TrAISformer) is exactly this. Surface/USV-relevant. |
| **B — the platform's OWN UUV systems** (the fleet-learning vision) | Onboard health/anomaly of an **unmanned vehicle's** subsystems (thrusters, battery/energy, ballast/trim, INS/DVL nav, leak, acoustic comms) | **NO — the machinery sets are proxies.** UCI #316 = frigate gas turbine, C-MAPSS/N-CMAPSS = aircraft turbofans, MetroPT = metro compressor. **No UUV.** And a *submerged* UUV gets no AIS (surface RF) — "AIS PoL on a UUV" is a category slip unless it's a surface USV. |

**The honest fix (for Framing B — the UUV own-systems demo):** train on a genuinely **UUV-shaped** source, not a jet engine:
- **BlueROV2 / ArduSub dataflash (MAVLink) logs** — real underwater-vehicle telemetry (battery V/I, thruster PWM, depth, attitude, leak), open + **self-capturable** by the team (the credibility difference).
- **IOOS Glider DAC / Rutgers Slocum** — real long-endurance AUV-class vehicle-health telemetry.
- **A UUV sim with fault injection** (HoloOcean / Stonefish / UUV-Sim) — fault-labeled thruster/battery/ballast/leak data at scale.
- Model: a small **sequence autoencoder** (LSTM/TCN/transformer; reconstruction-error = anomaly, supports RUL) — better than IsolationForest for streaming subsystem data. Train ashore (MLflow-tracked, GPU optional) → **ONNX-int8 → runs on the 4 GB Pi.**

**Owner:** Claire Shen (NAVSEA intern) trains the new UUV own-systems model on real UUV-shaped data (this supersedes the first AIS IsolationForest model, which moves to the Framing-A / NV063 surface-contact track). The fleet node registers it in **MLflow** and the flywheel coordinates it across Nodes 1+2. **The flywheel mechanism is data-agnostic** — it improves whatever model is registered; the *honesty* is in using the right data per framing.

---

## §5 — We're ~80% there (reframe, not rebuild)

| Already built + verified | Becomes |
|---|---|
| Fleet-learning miniature (poison rejected, eval-gate, signed) | the **UUV↔fleet-node loop** (ships→UUVs) |
| Edge serve + shore→ship delivery (`serve/`) | fleet node **pushes** models to vehicles |
| MLflow shore→ship sync (`deploy/mlflow-sync/`) | fleet node **pulls/coordinates** (the registry) |
| ONNX edge inference (`models/onnx/`) | the Pi-runnable lightweight models |
| Provenance-gated merge + eval-gate + in-toto/OSCAL record | the **safe, accreditable** coordination (the moat) |
| UI fleet-flywheel scene | the **unmanned fleet** flywheel |

So: **relabel ships→UUVs, wire the 2 real Pis as the vehicles, train the per-dataset models, run the loop through the fleet node.** The spine exists.

---

## §6 — The demo

2 Pis = 2 UUV brains running lightweight onboard models → **DDIL (disconnected)** → surface → **push signed deltas** to the fleet node → fleet node **coordinates via MLflow** (provenance gate **rejects a captured-UUV's poisoned delta**, eval-gate 0.0318→0.0300 PASS) → **push improved model back** → fleet improves. Shown on the digital-twin UI (the fleet flywheel). Every step **signed + sealed + OSCAL-mapped** (cATO-for-AI).

---

## §7 — Focus-area split (10-person team)

| Focus | Owner(s) |
|---|---|
| **UUV brains / analytics-on-Pis** (lightweight models + onboard inference) | NAVSEA + models |
| **Fleet node / MLflow coordination** (push/pull/merge/registry) | Tommy / Juan + NAVSEA |
| **Datasets → 8 lightweight models** | THESEUS agent + NAVSEA |
| **Deploy + wire the 2 Pis as UUVs** | William |
| **UI / digital twin** | Gerardo |
| **Security / accreditation / cATO-OSCAL** | Caroline |
| **Strategy / narrative / engagement** | Josh + Mark |

---

## §8 — Engagement doors (founder's lane; don't pitch DECK or PAE-RAS leadership directly)

PAE RAS **OTA Marketplace Roadmap** (accelerated OTA, <12-mo) · **platform integrators** (HII Unmanned, GD Mission Systems, Boeing Phantom Works — "fleet model coordination for Odyssey mesh") · **NAVWAR / Project Overmatch** AI/ML prize challenges. *(Founder is already connected into the PAE RAS room.)*

---

## §9 — Honest gates (unchanged)
Standard-emission ≠ AO acceptance (the sponsor conversation is the gate). The demo proves the **mechanism**; the fielded fleet is the multi-year roadmap. REMUS/Orca run pre-programmed autonomy today — position onboard learning as **enhancement**, not a claim they already do it.

*Sources: PAE RAS (USNI/InsideDefense/DefenseScoop), DECK (Applied Intuition/DefenseScoop), HII Odyssey/REMUS/Sea Launcher, Project Overmatch, Task Force 59, Tesla FSD data-engine + federated-learning literature (arXiv) — see `DECK_BLUE_OCEAN.md` + the research briefs.*
