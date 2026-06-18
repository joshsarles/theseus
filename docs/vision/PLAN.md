# THESEUS — the onboard ship-systems decision-support
### Warhacker · Team Force AI + NAVSEA · Jun 16–19 2026 · *living plan, we evolve as we go*

---

## The bet (share this)
A warship is a floating city of systems — propulsion, power, navigation, damage control, readiness — and the moment it loses the link to shore (DDIL: denied, degraded, intermittent, limited), all that data is on its own, scattered across stovepiped systems, watched by a handful of overworked sailors. **Theseus turns the ship into a self-controlled brain at the edge:** it ingests the ship's own systems data, fuses it into one live picture, spots what's failing or off-normal, and drafts the call for a human to approve — running fully disconnected, from one deployable bundle, with every decision written to a record nobody can quietly change. *Like the Ship of Theseus, every part can be replaced and she's still herself — because the brain that runs her is one.*

**One line:** the ship keeps thinking when it's cut off.

---

## Why this, why now
- **The team is the proof.** We have **NAVSEA + NSWC Port Hueneme engineers** — the people who actually build and sustain ship systems. This isn't outsiders guessing; it's the operators.
- **The host is already here.** Defense Unicorns (event host) + Leidos just won **Navy shipboard software-container trials (Apr 2026)**; the Navy fielded onboard AI condition-monitoring on **USS Fitzgerald (Jan 2025)**. The current is with us.
- **The gap is real (honest version):** onboard analytics today is single-system (engineering only) and mostly **feeds shore**. **Nobody has unified the ship's systems into one onboard brain that closes the loop locally under DDIL.** That's the white space.

---

## What we're building (scope, honest)
**v1 = the "SWAN side":** engineering / hull-mechanical-electrical / power / navigation / damage-control / readiness — the systems that ride the ship's own data bus (DDS). We **screen → correlate → detect anomalies → recommend → human approves → seal the record**, all disconnected.

- **Screen:** ingest the ship's live systems telemetry, full-auto
- **Correlate:** fuse scattered signals into one living picture of the ship's state over time
- **Detect:** flag the anomaly / impending failure before the watch does
- **Recommend, human commands:** draft the action; a sailor accepts or overrides; Theseus never acts on its own
- **Prove:** every call sealed in a tamper-evident, offline-verifiable record (doubles as accreditation evidence)
- **Deploy:** ships disconnected from one UDS/Zarf bundle, with NIST compliance evidence generated as it runs

**Explicitly out of v1 (say so):** combat-system data is hard-air-gapped and classified — we do **not** touch it in v1; that's a later classified variant. We pitch **decision-support + bounded autonomy, human always in command** — never "autonomous warship."

---

## What's already real (we don't start from zero)
The spine is built and verified — it transfers straight from our prior work:
- **Airgap deploy** (UDS/Zarf → disconnected cluster, compliance evidence) — *verified running*
- **Tamper-evident, offline-verifiable record** (hash-chained, tamper-snaps) — *verified*
- **Correlation/anomaly engine** (fuses noisy signals into tracks/state over time) — *verified*; we re-point it from imagery detections to ship-systems telemetry
- **A live console** (the watch picture + human accept/override) — *built*
- **One-command laptop setup** (`make onboard`) + IP-guard firewall — *built*
Repo: **github.com/joshsarles/theseus** (private).

## What we build in 4 days
1. **Ship-systems data adapter** — feed real/representative shipboard telemetry (DDS/SWAN-style: power, propulsion, nav, damage-control) into the correlation engine
2. **Anomaly + "ship normal" model** — learn the ship's normal, flag the off-normal (this is where the NAVSEA engineers' knowledge is the moat)
3. **The watch console** — one live picture of ship state + the recommend/accept/override beat
4. **Disconnected demo** — pull the cord (simulate DDIL), show Theseus keeps thinking and the record holds
5. **Deploy story** — the whole thing from one airgap bundle with compliance evidence (≈half the rubric, already built)

---

## The team & roles (we flex as we go)
*Real names + specific commands kept OUT of this public repo (OPSEC); the canonical roster lives in the team channel. NAVSEA/NIWC/NSWC engineers + analysts (9).*
| Who | On Theseus |
|---|---|
| **Joshua** | Lead — narrative, architecture, the demo, the deploy spine |
| **William** | Ship-systems domain lead (what data matters / what "normal" is) + edge / Pi cluster + SDR |
| **Tommy** | In-service ship-systems engineering (real failure modes); build / MLOps |
| **Carolina** | Security / IL6 baseline; analyst voice — the human in the loop, readiness |
| **Nicholas** | Models — prototype engineering / build |
| **Juan** | Networking / MLOps |
| **Savannah** | Ship-systems engineering / data; eval / labeling |
| **Gerardo** | Frontend |
| **Aaron** | Data + frontend / analytics |

*Defense Unicorns engineers on-site = the deploy/UDS muscle if we want it.*

---

## The 4 days
- **Day 0 (tonight):** lock the team, `make onboard` green on every laptop, agree the one ship-systems workflow we demo (NAVSEA engineers pick the failure story).
- **Day 1:** data adapter + "ship normal" anomaly engine + console shell. First disconnected deploy.
- **Day 2:** full loop — screen → correlate → detect → recommend → human approves → record; pull-the-cord DDIL demo; lock the deploy under 90s.
- **Day 3:** freeze, record the run, dry-run the outbrief twice, deliver.

---

## Discipline (non-negotiable)
- **Human always commands.** Theseus recommends; the sailor decides. Never "autonomous ship control."
- **Decision-support + bounded autonomy**, off combat systems / weapons / propulsion-survivability decisions.
- **Real, not mock** — real or representative ship telemetry, stated. Nothing fabricated shipped.
- **Integrate, never replace** — we ride on the ship's data bus and complement existing systems (incl. the Navy's onboard monitoring), never displace them.
- **Don't overclaim:** others do onboard ship edge AI (Applied Intuition's "DECK" collects onboard + feeds shore). Our line is narrow and true: *no one closes the loop locally across all the ship's systems under DDIL.*

---

## The win condition
A judged, live demo of a ship that keeps thinking when it's cut off — built by the engineers who run the ships — deployable to any vessel from one bundle, with a record you can trust. That's the room, and it's the start of something real.

*This plan evolves. Drop reactions/edits in the channel — Day 0 is for shaping it together.*
