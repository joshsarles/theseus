# THESEUS — Fleet-Learning Vision & the Path to 10/10

*The founder's vision (a ship that is a city of its own, learning locally under DDIL, syncing to a fleet brain when safe so the whole fleet improves) grounded against the current SOTA and the Navy's own programs. Web-researched Jun 17 2026. Companion to `BUILD_VISION.md` (the wedge), `../INTEGRATION_SPEC.md` (the components), and `../WARHACKER_JUDGE_AUDIT.md` (the scoring). Drafted by the THESEUS lane.*

> **One line:** Each ship learns its own systems locally, airgapped. When it is safe (not contested), ships sync model updates (never raw data) to a fleet brain; the fleet brain merges only **provenance-attested, eval-gated** contributions and pushes a better model back. Every contribution, merge, and promotion is sealed in a tamper-evident, replayable record. The result is fleet-scale continual improvement that a human can command and an accreditor can sign.

> **The unification that makes it 10/10:** the tamper-evident record is not a side feature. It is the thing that makes safe fleet learning *possible* and *accreditable*. The moat and the vision are the same artifact. Sections §3 and §4 are why.

---

## §1 — The vision, stated cleanly (and honestly)

- **The ship is a city.** Each major subsystem (machinery / power / propulsion / navigation / damage-control / contacts) carries its own onboard anomaly model. A master ship brain fuses them into one live ship-state and reasons across them.
- **Local-first, airgapped.** The ship learns its own idiosyncrasies (this hull's #2 gas turbine runs hot) with no internet, fully under DDIL. Disconnected is the baseline; the shore link is the bonus.
- **Recommend, human commands.** Subsystems surface **recommended interventions** to the watch team. The human decides; THESEUS never acts on its own. (Language discipline in §8: never "autonomous intervention.")
- **Sync when safe.** When the ship is not in a contested environment, it syncs **model updates, not raw sensor data** to a fleet brain. Choosing *when* to sync is itself a security control.
- **The fleet improves as one.** The fleet brain merges contributions from many hulls and pushes an improved model back, so a lesson learned on one ship benefits all. The Tesla-fleet-learning analogy, applied to warships, but **eval-gated, provenance-attested, and human-authorized** so it improves *safely*.

---

## §2 — Why now: the Navy is already saying this out loud (partner, do not compete)

The single most important finding: **the Navy has publicly stated this exact vision and is funding the front half of it. Nobody has closed the loop.**

- **DECK (Applied Intuition, delivered Mar 19 2026)** is explicitly meant to *"turn Navy ships into 'learning systems'"* (FedTech, WEST 2026) and *"continuously gathers and manages data the service can use to build better AI algorithms"* (DefenseScoop, 2026-03-19). It is a cornerstone of the **Warfighting Data Ecosystem** (part of PAE RAS).
- **WEST 2026, verbatim:** *"The Golden Fleet needs a way to use data gathered at the tactical edge to **retrain** AI models supporting operations **underway**."* That is the founder's vision, in the Navy's words.
- **Project Overmatch** is the Navy campaign to accelerate AI/ML delivery to the fleet. DoN CDAO Stuart Wagner (Breaking Defense, 2025-08-14): the Navy must *"access and analyze the masses of sensor data currently languishing aboard its aircraft, warships."*

**The seam THESEUS owns:** DECK is the *data pipe* (collect at the edge → ship to shore → retrain ashore). It **opens** the loop. It does not (a) learn onboard under DDIL, (b) do the **provenance-gated safe fleet-merge**, or (c) make the updating model **accreditable**. THESEUS **closes** the loop and plugs *into* the Warfighting Data Ecosystem. Be the payload that closes DECK's loop, not a competitor to DECK. This is the "be the payload, not the pipe" pattern from `INTEGRATION_SPEC.md §5`, at fleet scale.

---

## §3 — The core idea: the record is what makes fleet learning accreditable

Fleet learning has two killers in a defense context. The record kills both. That is why it is load-bearing, not decorative.

**Killer 1 — model poisoning (the security problem).** In federated learning, one compromised or captured node can poison the global model (well-established: Fang et al., *Local Model Poisoning Attacks to Byzantine-Robust Federated Learning*, USENIX Security 2020; and a 2025-2026 literature, e.g. MDPI *Sensors* 26/4/1275, 2026-02-15). A warship is a real capture/loss threat model. **THESEUS's answer:** the fleet brain merges **only** contributions carrying a valid attestation. Provenance-gated aggregation is a defense-grade answer to Byzantine poisoning, and because the ship chooses when to sync, a compromised hull's contributions can be quarantined or revoked. "Verifiable federated learning" is exactly the active research front (Frontiers, *A robust and verifiable federated learning framework*, 2026-02-13); THESEUS's signed record is the verification substrate.

**Killer 2 — you cannot accredit a model that changes (the ATO problem).** Traditional ATO freezes a system; a continuously-learning model breaks that. This is the Navy's actual #1 AI blocker under an AI-first, wartime-speed mandate (Pentagon AI Strategy, 2026-01; DoW AI-first agenda, HK Law 2026-02; the Army is "on the cusp" of continuous ATO for software, Federal News Network 2026-04-07). **THESEUS's answer:** accredit the **pipeline's provenance, not the static weights.** With **cATO** (Continuous Authorization to Operate; DoD memo 2022-02-03) plus a tamper-evident, replayable record of every training contribution, every merge, and every promotion, you accredit the *process* once and every compliant update inherits the path. The record emits in the AO's own language (NIST **OSCAL** via Lula; `INTEGRATION_SPEC.md §2`) and the supply-chain standards the DoD already mandates (in-toto / SLSA / Sigstore).

**The synthesis:** safe fleet learning *requires* provenance-gated merge + eval-gated promotion + replayable history. That is precisely the record THESEUS already built. So the vision does not add a new moat; it reveals that the moat we have is the enabler of the biggest version of the mission. The record is the trust fabric for fleet learning.

---

## §4 — The honest hard problem: catastrophic forgetting (and why our existing primitives are the defense)

"The fleet just keeps getting better, like Tesla" is the vision; naive continual learning **regresses** (catastrophic forgetting: a model learning new things overwrites old knowledge). This is a live 2026 research problem (Turingpost, 2026-06-08, *Why AI Models Need Sleep*; arXiv 2601.21861, *Spatiotemporal Continual Learning for Mobile Edge UAV Networks*, 2026-04-07; "de-risk updates without retraining from scratch," Adnan Masood, 2026-02).

**Do not claim "it just improves." Claim "it improves safely, because every update is gated."** The three gates are primitives THESEUS already has:
1. **Eval-gated promotion** — a merged/updated model must beat the incumbent on a held-out set before it is accepted (the `deploy/ddil_beat.sh` acceptance-gate pattern, generalized to the fleet merge).
2. **Rollback-to-last-good** — any node can revert instantly, offline (already built + verified).
3. **Provenance record** — every version's lineage (trained on what, merged from whom, approved by whom) is replayable, so regressions are traceable and revertible.

So the catastrophic-forgetting risk is real, and our answer is concrete and already-built: gate, attest, roll back. That honesty is itself a Judges-Pick asset in a CDAO/DU room.

---

## §5 — The architecture (how the pieces compose)

Three tiers, all on components from `INTEGRATION_SPEC.md` (build only the glue):

1. **Subsystem organs (per-system, onboard edge).** Each subsystem runs its own small anomaly model (PyOD / Merlion / River; ONNX on a 4GB-class node). Recommends, human commands.
2. **Master ship brain (onboard, DDIL).** Fuses organs into one ship-state (Stone Soup cross-system fusion + automerge CRDT for partition-tolerant state + Zenoh, with its DDS plugin reading the SWAN-side ship bus). Runs the local learning + the eval-gate + the rollback. Seals everything to the record.
3. **Fleet brain (shore / squadron, syncs when safe).** Aggregates **attested** model deltas from many hulls (Byzantine-robust + provenance-gated merge), eval-gates the global model, signs it (in-toto / SLSA / cosign), and pushes it back via **UDS Fleet + Tactical Edge**. The whole exchange is OSCAL-recorded as cATO evidence.

The data that crosses the link is **model updates + attestations, never raw sensor data** (federated-learning's core property is also the contested-environment property: nothing sensitive leaves the hull).

---

## §6 — The miniature that PROVES it at the event (the creative unlock)

A hackathon cannot field a real fleet in four days, but the hardware on hand maps perfectly to a miniature that demonstrates the *entire* loop at small scale, live:

- **Pi-1 and Pi-2 = two "ships."** Each learns its own machinery/contacts model locally, airgapped (cord pulled).
- **Ryzen (or the Mac) = the "fleet brain."**
- **The beat:** pull both ships' cords → each learns something locally → "safe to sync" → each ship contributes a **signed** model delta → fleet brain **merges only the attested deltas** (show an **unsigned/poisoned delta REJECTED** at the merge) → eval-gate the merged model → push it back → both ships are now better → every step seals into the record → tamper one byte → the chain SNAPs.

That miniature *is* the 10/10 demo: it shows fleet learning, DDIL-local autonomy, the provenance-gated safe merge (the poisoning defense), the eval-gate (the forgetting defense), human-in-command, and the accreditation record, on real hardware, disconnected. It turns the grand vision into something a judge watches happen on a table.

---

## §7 — The path to 10/10 (what "10" looks like per dimension)

| Dim | Wt | 10/10 = | The lever |
|---|---|---|---|
| **Mission Impact** | 25% | Not "anomaly detection on one ship" but "the loop that closes DECK/Overmatch: the fleet that learns from every hull, safely, under DDIL." Existential-scale, in the Navy's own words. | Demo the fleet-learning miniature (§6) + frame against DECK as the loop-closer. |
| **Portability** | 25% | The fleet sync **is** portability at its conclusion: deploy to any hull, it joins the fleet brain via UDS Fleet. | Full uds-core live + the 2-ship→fleet-brain sync shown + UDS Fleet composition. |
| **Death Proof** | 25% | The reframe that wins it: **"we make a *learning* model accreditable" (cATO for AI via provenance).** The valley of death solved structurally, plus an attributed AO sentence. | Show the OSCAL/in-toto provenance gating the merge; land one AO/PEO sentence that the pipeline is accreditable. |
| **Most Resourceful** | 15% | Composed best-of-breed, built only the Navy-specific glue, demonstrated the whole fleet loop on 2 Pis, caught own bugs. | Already near-max; the miniature seals it. |
| **Judges Pick** | 10% | "Tesla fleet learning for the Navy, but accreditable and human-commanded, built on the UDS Fleet you launched two weeks ago." | The vision + the honesty + riding their newest product. |

**10/10 is a ceiling, not a forecast.** It requires: the §6 miniature landing clean live, the cATO-for-AI framing resonating with the CDAO judges, and the AO sentence. Realistic well-executed is ~7.8 (`WARHACKER_JUDGE_AUDIT.md §0.1`); this vision is what raises the *ceiling* from ~8.5 to 10 by changing the category from "onboard tool" to "fleet-learning substrate."

---

## §8 — Language & safety discipline (the traps that kill this with these judges)

The vision contains words that, said wrong in a DU/CDAO room, trigger the safety review that ends the pitch. Hold these lines:

- **"Intervention" → "recommended intervention, human-in-command."** The founder's "intervention" must always be advisory. Never "autonomous intervention," never "the AI acts."
- **"The fleet updates itself" → "the fleet improves under human-authorized, eval-gated, provenance-attested sync."** Never imply the fleet model changes without a human gate and an eval gate.
- **"Self-controlled / ship brain (external)" stays banned** (per `BUILD_VISION.md`; already scrubbed from public surfaces). Internal north-star language only.
- **Keep SWAN-side.** Combat-system data is hard-air-gapped/classified; v1 is engineering/contacts only. The fleet-learning story stays SWAN-side until a later classified variant.
- **Sync-when-safe is a security feature, not a limitation.** Frame the ship choosing its sync window (not during contested ops) as reducing the fleet-wide attack surface.

---

## §9 — Honest risks & open questions

- **Demonstrable vs claimed.** The §6 miniature is real and landable; the *fleet at scale* is the arc, not the event. Judges score the miniature + the path's credibility. Label it honestly.
- **cATO-for-AI is a strong claim, not a delivered fact.** No AO has signed THESEUS's record as cATO evidence yet. The claim is "the provenance pipeline is the mechanism cATO needs," which is defensible; the proof is the sponsor conversation.
- **Byzantine-robust aggregation is non-trivial.** Provenance-gating raises the bar but is not a complete poisoning defense on its own; pair it with a robust aggregation rule (named, from the FL literature) and say so.
- **Catastrophic forgetting is unsolved in general.** Our gate/rollback/attest answer is sound for *safe* updates; do not claim we solved continual learning.
- **DECK/Overmatch could extend into the loop.** Applied Intuition is funded and close. Mitigation: own the onboard-DDIL learning loop + the accreditation record (the hard, Navy-specific, provenance-gated part), and integrate rather than collide.
- **Open verification:** does UDS Fleet expose per-node model/attestation push-pull (the fleet-brain transport)? Confirm before leaning on it (`INTEGRATION_SPEC.md §5`).

---

## §10 — Sources (web-surfaced Jun 17 2026; titles/venues/dates confirmed, deep-read is a follow-up)

- **Navy programs:** DefenseScoop "Navy program turns ships into continuous data pipelines" (2026-03-19); FedTech "WEST 2026: DECK Will Turn Navy Ships Into 'Learning Systems'" (2026-02-16); TheDefensePost "Navy's New AI Data Engine Turns Ships Into Self-Learning [Systems]" (2026-03-23); Applied Intuition DECK press (2026-03-19); Breaking Defense "New Navy-Marine AI and data strategy" (Stuart Wagner, 2025-08-14); Seapower "Navy Aims to Fast-Track AI/ML" (Project Overmatch).
- **cATO / AI accreditation:** DoD "Continuous Authorization To Operate (cATO)" memo (2022-02-03, media.defense.gov); Federal News Network "Army's Leo Garciga on continuous ATO" (2026-04-07); Pentagon AI Strategy (2026-01-12, media.defense.gov); HK Law "Department of War's AI-First Agenda" (2026-02); DoD Manual 5000.101 (OT&E of AI-enabled systems).
- **Federated learning (defense + edge):** AFCEA SIGNAL "Decentralized Defense: How Federated Learning Strengthens U.S. [defense]" (2025-06-02); MDPI *Sensors* 26/4/1275 "Federated Learning in Edge Computing: Vulnerabilities, Attacks" (2026-02-15); "Federated Learning's 2026 Moment" (Medium, 2025-11); Federal News Network "The tactical edge is now" (2026-04-16).
- **Model poisoning / verifiable FL:** Fang et al. "Local Model Poisoning Attacks to Byzantine-Robust Federated Learning" (USENIX Security 2020); "Manipulating the Byzantine" (NDSS 2021); Frontiers "A robust and verifiable federated learning framework" (2026-02-13).
- **Continual learning / catastrophic forgetting:** Turingpost "Continual Learning in LLMs: Why AI Models Need Sleep" (2026-06-08); arXiv 2601.21861 "Spatiotemporal Continual Learning for Mobile Edge UAV Networks" (2026-04-07); Zylos "Continual Learning and Catastrophic Forgetting Prevention" (2026-04-09); Adnan Masood "Continual Learning: The Missing Capability" (2026-02).
