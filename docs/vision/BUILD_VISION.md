# THESEUS — Build Vision & Decision
*Synthesis of the 4-lens design council (Architect / Visionary / Strategist / Red Team), Jun 17 2026. This is the decision, not a menu.*

## North star (the vision, internal)
The **cognitive layer for a warship** — the onboard nervous system that fuses a ship's own systems into one live picture, reasons across them locally, and keeps reasoning when the link to shore is cut. A ship that stays mission-capable, self-diagnosing, and self-healing under DDIL — **always under human command.** The category, long-term: the *self-controlled platform brain* for every contested-environment platform (ship → fleet mesh → subs/ground/air).

## The honest external framing (Red Team won this — non-negotiable)
We do **not** say "self-controlled ship brain" outside. The headline contradicts the rails and invites the safety review that kills us. The honest, defensible pitch:
> **An airgapped, tamper-evident onboard decision-support substrate.** It deploys from one signed bundle to a disconnected hull, fuses available **SWAN-side** sensor/machinery data, flags known fault signatures + behavioral deviations **for watch-team review** (human-in-command), and keeps a cryptographically verifiable, replayable record that survives DDIL and syncs on reconnect. It runs **alongside** existing systems (Fathom5/DECK/IPMS), never replacing them.

Drop these claims: "controls the ship," "fuses ALL systems" (combat data is air-gapped/classified — SWAN-side only in v1), "detects any anomaly cold" (→ "known signatures + flagged deviations, with a watch-tolerable false-alarm rate").

## What we build FIRST (Architect + Strategist consensus): the Local Anomaly Cell
One containerized, SWAN-side, **zero-shore-dependency** service:
> real **AIS + ADS-B** (over-the-air via SDR) + **radar** (sim) → **cold-start Pattern-of-Life** anomaly → **explainable alert + recommended action** → sealed in the **tamper-evident record** → runs fully disconnected.

It passes all three tests: **(a)** demos at Warhacker (visceral, watch-officer-legible), **(b)** maps almost line-for-line to **NV063**, **(c)** is the seed of the platform — swap the model for NV061 predictive track, add the engineering organ, each new algorithm a tenant on the same substrate.

## The moat (Strategist + Visionary, emphatic): the RECORD, not the ML
The ML (anomaly detectors, track predictors) is **commoditized** — a prime clones it in a quarter. The defensible franchise is the **tamper-evident, explainable, replayable record as the accreditation/trust substrate.** The Navy's blocker to fielding onboard AI is *trust + accreditation*, not accuracy. Own the evidence layer and every other algorithm (ours, Fathom5's, even a prime's) must emit into it to be trusted onboard → we become infrastructure. **Build the evidence layer like it's the whole company.**

## Architecture (the Architect — and a big reuse find)
- **Edge fabric:** a mesh of nodes, one cluster per subsystem organ (NAV / PWR / PROP / DC / RDY) + floating FUSE (correlation) + WIT (record) roles that re-elect on node loss. Demo HW = Raspberry Pi 5 + AI HAT+2 (40 TOPS); **production HW must be named ruggedized/MIL-STD compute — the Pi is a demo, not a deployed-warship claim.**
- **Shared state = a CRDT** (LWW/OR-set/G-counter), not a database → partition-tolerant, merges on reconnect with no consensus round-trip. **DDIL-by-construction; disconnected is the baseline, shore link is the bonus.**
- **Transport:** Zenoh (pub/sub/query for constrained/intermittent links).
- **Ingestion:** read-only DDS participant on SWAN + thin per-subsystem adapters → one canonical `Observation` schema (quantity + unit + provenance + freshness).
- **Brain:** physics/doctrine priors (useful at t=0) → online streaming detectors (self-calibrate) → in-situ Pattern-of-Life. Cross-silo correlation into one ship-state (the reason Theseus exists). Predictive forecasting. **Recommend → human-approve → log.**
- **Explainer:** a small LLM **distributed across the cluster** (turns a structured event + evidence into a plain-language alert + recommended action) — narrator over deterministic findings, never the decider.
- **🔑 REUSE Seahelm** (`/Users/force/Developer/Force/Projects/Seahelm/`): it already has FIPS-grade hash-chained signed record, CRDT/DDIL doctrine + authority-decay, Zenoh transport, the adapter pattern (incl. DDS/UMAA), an ONNX anomaly runtime, and edge-K3s deploy. **Fork these primitives; don't re-derive.** (Seahelm governs a fleet of vehicles from above; Theseus is the brain inside one hull — they meet only at manned-unmanned teaming.)

## Tech stack (founder-set + how it slots in)
- **Python + PyTorch** — the models (anomaly detectors, PoL, track prediction). Export to **ONNX** for the edge runtime (Seahelm's ONNX path / Pi NPU).
- **MLflow** — experiment tracking **and the model registry**. This is the backbone of the **DDIL model lifecycle**: versioned, signed, content-addressed weights → pre-staged in the bundle → rollback-to-last-good on a disconnected ship → the loaded version recorded in the trust chain. MLflow registry ↔ the record is a clean fit.
- **Docker + k3s** — container build/runtime (Docker) under **k3s** (lightweight Kubernetes) on the nodes. Builds the images the **UDS/Zarf** airgap bundle ships.
- **Force OS** (force-core) — the fleet/agent orchestration option for the per-node agent mesh + A2A; **APOLLO is proving Force OS on an NVIDIA Blackwell cloud box with self-hosted Kimi 2.7** (the model-hosting/inference proof). Force OS is the orchestration substrate; Seahelm is the DDIL edge/record core; they compose.
- **UDS / Zarf** — the airgap deploy bundle (already verified end-to-end).

## The two things that actually decide life-or-death (Red Team — chase these, not the demo)
1. **A program-office sponsor who owns the ATO risk** (NOT just a SBIR TPOC). No sponsor → a clean bundle sits in a lab forever. *Single most likely cause of death.* The NAVSEA + retired Navy/Marine team is the path to this — use them.
2. **A contractual/technical path to one real ship-data feed past the primes** (signed ICD or interface agreement). "Fuses ship data" is unproven until we name the feed. Start SWAN-side machinery telemetry (most reachable).
   Plus: **a false-alarm number** on real/high-fidelity machinery data at a watch-tolerable threshold (<~1 nuisance/watch) — trust is a one-shot resource on a ship.

## Partner vs compete
- **Partner for plumbing:** Defense Unicorns (UDS airgap deploy), Fathom5/ERM v4 (host the cell as a module → back-door onto a real hull while ICS cert matures), Edgerunner (on-device LLM as the NL interface, v2).
- **Own:** the trust substrate + the local close-the-loop.
- **Avoid head-on:** Palantir (own the disconnected-ship seam they're weak on); primes (win NV063 independently first, then let them sub *us*).

## Sequence (0 → 6 → 18 months)
- **0–6 (Wedge):** build the Local Anomaly Cell on real AIS/ADS-B; lock the record format as the product; demo at Warhacker on representative DDIL hardware; submit **NV063**; deploy via UDS; open Fathom5 hosting + hunt a program-office sponsor.
- **6–12 (Beachhead):** field as a hosted module on ERM v4; begin ICS containerized-module cert; add **NV061** as the 2nd tenant on the same substrate; turn the record into reusable ATO-evidence artifacts.
- **12–18 (Platform):** open the substrate to third-party algorithms that must emit into the record to be trusted; convert independent proof into a prime subcontract on our terms / Phase III.

## The line that ties it together
Win the **wedge** with one capability on real data, airgapped, with the record. Win the **category** by being the trusted onboard substrate every algorithm emits into — under human command, always. *The ship persists because its identity persists.*
