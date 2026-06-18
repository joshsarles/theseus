# THESEUS — Onboarding (boot up · pull · learn · contribute)

*For new teammates (Mark + anyone joining). Zero → contributing in ~20 minutes. The whole system was built with an AI copilot that knows this codebase + the strategy cold — **boot it up and ask it anything.** It's the fastest way in.*

---

## TL;DR — what THESEUS is
**The accreditable fleet-learning layer for unmanned maritime vehicles under DDIL.** Each UUV learns locally while it's cut off from comms; a **fleet node** coordinates the improvements (it merges *model deltas*, never raw data); and **every model update + human decision is sealed in a tamper-evident, standards-based record (in-toto / NIST OSCAL) an accreditor can trust.** Think *Tesla-FSD-for-a-UUV-fleet* — but DDIL-native and **accreditable**, which is the part nobody else has. The Navy's data engine (DECK) *opens* that loop; THESEUS *closes* it and proves it.

---

## 1. Pull the codebase
```bash
git clone https://github.com/joshsarles/theseus.git
cd theseus
git pull            # pull often — the team pushes continuously
```

## 2. Boot up the copilot (your fastest path in)
The build is driven by an AI copilot (**Claude Code**) that has full context of this repo.
```bash
# install once:  https://claude.com/claude-code   (or: npm install -g @anthropic-ai/claude-code)
cd theseus
claude            # starts the copilot IN the repo — it reads the docs + code as context
```
Then just **ask it** (it answers from the actual code + docs):
- *"Explain THESEUS in 2 minutes — the mission, the architecture, the moat."*
- *"Walk me through the 3-node topology and the fleet-learning flywheel."*
- *"What's real and verified vs. in-progress? Prove it with `deploy/preflight.sh`."*
- *"What's my lane (strategy / engagement) and where's the highest-leverage thing I can do this week?"*
- *"Run the demo and explain each beat."*

## 3. See it run (5 minutes)
```bash
bash deploy/demo_up.sh                       # brings the demo to GO (record + API + preflight gate)
cd frontend/ui && npm install && npm run dev # the UI → http://localhost:5173
#   OPERATIONS scene = the ship/UUV digital twin · FLEET LEARNING scene = the flywheel
bash fleet/run_miniature.sh                  # the flywheel: local learn → merge → eval-gate → sealed (poison delta REJECTED)
python3 -m pytest tests/                     # 21 tests
```

## 4. Read these, in order (the map)
1. `README.md` — the front door
2. `docs/vision/UUV_FLEET_ARCHITECTURE.md` — **THE locked plan** (what we're building, the 3-node topology, the data-honesty fork)
3. `docs/vision/FLEET_LEARNING_VISION.md` — the big vision (why this is a 10/10 category, not a tool)
4. `docs/research/DECK_BLUE_OCEAN.md` — the market + why the lane is genuinely open
5. `docs/INTEGRATION_SPEC.md` — buy/borrow/build (we compose best-of-breed, build only the Navy-specific inch)
6. `ROADMAP.md` — state, phases, and the update log (newest on top)
7. `docs/TEAM_LANES.md` — who owns what

## 5. The architecture (30-second version)
- **Node 1 + Node 2 = the 2 UUVs** (Raspberry Pi 5 brains) — run lightweight models locally, **airgapped** (submerged = denied comms).
- **Node 3 = the fleet coordinator** (the demo Mac) — hosts **MLflow** (the model registry) + the **UI**; aggregates the UUVs' learned improvements, **eval-gates** the best, pushes it back down.
- **The loop (flywheel):** learn local → push **signed deltas** → **merge** (provenance-gated — a captured/poisoned node is *rejected*) → **eval-gate** (a worse model never ships — you can't recall it from a submerged vehicle) → push back. The **record** makes every step accreditable (cATO-for-AI).

## 6. Your lane, Mark — strategy / engagement (with Josh)
- Use the copilot as a force-multiplier: ask it to **draft** (one-pagers, briefs, decks), **research** (it web-searches + cites), and **red-team** (it'll poke holes honestly). It built most of this and knows the honest framing.
- Start with: *"Give me the current strategy state and the 3 highest-leverage things in the strategy/engagement lane."*
- Engagement/relationships are the founder's lane — coordinate with Josh; don't free-lance outreach.

## 7. The disciplines (non-negotiable — and the copilot will hold you to them)
- **Human always in command** — THESEUS *recommends*; a human decides. Never "autonomous."
- **All-real** — no mocked/fabricated data or results. A proxy or an in-progress thing is *labeled* as such.
- **No overclaim** — concede limits out loud (it reads as credibility). The fleet-learning is *demonstrated in miniature*; the fielded fleet is the roadmap.
- **Data honesty** — *Framing A* = what the platform **watches** (surface/air contacts; AIS data, real) vs *Framing B* = the platform's **own UUV systems** (needs real UUV telemetry, not jet-engine proxies). Don't conflate them.
- **OPSEC** — **no real names or specific commands in the public repo.** (Roster + commands live in the team channel only.)

## 8. Where we are (snapshot — `ROADMAP.md` is authoritative)
Verified + on `main`: the tamper-evident **signed record** (in-toto/DSSE + Ed25519), the model-delivery loop, the **fleet-learning flywheel** (provenance-gated merge, poison rejected, eval-gate, verifies), the **digital-twin UI** (OPERATIONS + FLEET LEARNING), real **airgap UDS deploy** (Zarf + SBOM + cosign + live Pepr admission), ONNX edge inference (fits a 4 GB Pi), the OSCAL/cATO compliance emit, and a clean CodeQL security tab. **In flight (the team's lanes):** a real **UUV-shaped** dataset + Claire's **sequence-autoencoder** model (registers in MLflow as `theseus-uuv`), the live **MLflow** server on Node 3, and the 2 Pis as live UUV nodes. Team = 11.

---
*Stuck? Boot the copilot and ask. It runs overwatch on Node 3 and keeps the repo coherent — `git pull` before you start, and push small + often.*
