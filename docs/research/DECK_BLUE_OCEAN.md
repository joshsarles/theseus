# DECK Deep Dive & the THESEUS Blue Ocean

*Deep research on Applied Intuition's DECK, its parent acquisition structure, and Applied Intuition's roadmap, to locate the uncontested space THESEUS can own for the fleet-learning vision. Web-researched Jun 17 2026. Companion to `../vision/FLEET_LEARNING_VISION.md` and `../INTEGRATION_SPEC.md`. Drafted by the THESEUS lane.*

> **HONESTY-FIRST note on sourcing:** the Applied Intuition press page is a JS-rendered SPA that redirects on fetch, so DECK capabilities below are drawn from consistent secondary coverage (DefenseScoop, FedTech/WEST 2026, TheDefensePost, hstoday, techbytes, PRNewswire syndication) rather than the verbatim release. PAE RAS scope is from Naval Sub League, usvhub, and Breaking Defense. Applied Intuition roadmap is from their own product pages + the CDAO selection. Claims are labeled [verified across sources] or [inferred]. Deep-reading the primary DefenseScoop/FedTech articles is a follow-up.

---

## §1 — Executive summary (the blue ocean in four sentences)

DECK is a **data engine**: it collects, curates, and moves ship sensor data so models can be built and operations supported, centered on **unmanned/autonomous systems** (it sits under the Navy's robotics-and-autonomy acquisition portfolio). It opens the learning loop; it does not close it onboard, it does not make a learning model accreditable, and it does not solve safe fleet-merge. The uncontested space, the blue ocean, is the intersection of **onboard closed-loop learning under DDIL + the provenance record as accreditation evidence (cATO-for-AI) + provenance-gated fleet-merge + the ship-systems-engineering (HM&E) domain** — none of which DECK does, all of which require exactly a NAVSEA/NIWC team, and all of which *ride* DECK rather than compete with it. The one-liner: **DECK feeds the loop; THESEUS closes it and proves it.**

---

## §2 — What DECK actually is [verified across sources]

Consistent capability description across all coverage:
- **Collects + processes live sensor data** continuously at the tactical edge.
- **Overlays actionable info for operators** (a console/SA layer).
- **Manages satellite bandwidth** to prioritize what gets handled and delivered (the constrained-link data-triage problem).
- **Continuously gathers + manages large data** to "build better AI algorithms and autonomous systems" and to "shorten the AI development cycle."
- Framed as turning ships into "continuous data pipelines" / "learning systems" by getting edge data back to where models are retrained.

In one phrase: **DECK is the plumbing that turns a ship's sensor exhaust into curated, bandwidth-managed data that feeds the AI development pipeline.** Delivered Mar 19 2026 (Applied Intuition's "first large-scale data engine"); a cornerstone of the Navy's **Warfighting Data Ecosystem**.

---

## §3 — The parent structure (why it matters for capture)

- **PAE RAS = Portfolio Acquisition Executive for Robotic and Autonomous Systems.** A Navy acquisition-reform construct that consolidates **~50-66 unmanned programs across ~18 offices** under one acquisition authority (Naval Sub League, Dec 2025; usvhub; Breaking Defense, "Navy unveils acquisition reform, establishes five more PAEs," 2026-03-17). DECK is "part of PAE RAS."
- **Center of gravity = unmanned/autonomy.** PAE RAS is robotics-and-autonomous-systems. So DECK's gravity is **autonomy/USV data**, not the manned-ship engineering plant. [inferred but strongly supported]
- **Live capture vehicle:** a **PAE RAS Industry Day (June 2026)** is posted on sam.gov (2026-05-21), and the PAE RAS office is "gearing up to release a roadmap to industry" (DefenseScoop, 2026-04-22). This is an open door, and a NAVSEA team is adjacent to it.
- **Broader context:** Information Superiority Vision 2.0, GenAI.mil, "nerve centers," DON Digital Warfighting Symposium (May 2026), USNI's "culture of continuous learning." The Navy is all-in on continuous learning + data fluency. The ecosystem is forming now.

---

## §4 — Applied Intuition's DNA & roadmap (why they likely will NOT fill the gap)

- **DNA = autonomous vehicles + simulation + "physical AI."** Core products: Self-Driving System (SDS), Vehicle OS, tools for vehicle intelligence. Defense line: **Acuity** ("complex kill chains through trusted autonomy"), **Axion** (all-domain vehicle intelligence). Series F; CDAO selected them in May 2026 to build an enterprise capability.
- **Their roadmap vector is autonomy + kill-chain + simulation**, not ship-systems-health (HM&E) and not a per-decision accreditation/trust substrate. [inferred from their product portfolio + program alignment]
- **Implication:** the engineering-plant health domain and the accreditation-record layer are off Applied Intuition's center line. They are far more likely to extend DECK deeper into autonomy-data + simulation than into "make a NAVSEA engineer's learning model accreditable onboard under DDIL." That is the durable gap.

> Caveat (honest): a Series F autonomy leader with a CDAO enterprise deal *could* extend in any direction. The defense is to own the part that is hardest for an autonomy-data company to reach: the NAVSEA-domain HM&E knowledge + the accreditation relationship + the onboard-DDIL trust loop.

---

## §5 — What DECK structurally does NOT do (the gap map)

1. **Close the loop onboard under DDIL.** DECK collects-and-moves; it assumes data can be triaged and delivered. It does not run learn → recommend → human-decide → update → rollback **on a disconnected hull that cannot move data**. The contested-DDIL case is exactly where a data-mover has the least to offer.
2. **Make a learning model accreditable.** DECK is a data engine, not a trust/accreditation substrate. It does not answer "how does the Navy field a model that *changes*?" (the cATO-for-AI problem). No provenance record that an AO signs.
3. **Safe fleet-merge (Byzantine-robust + provenance-gated).** Moving data is not merging learning safely. DECK does not solve "merge contributions from many hulls without one compromised ship poisoning the fleet model, and prove it."
4. **The ship-systems-engineering (HM&E) domain.** DECK/PAE RAS gravity is autonomy/USV. Machinery, power, propulsion, damage-control health, the manned-combatant engineering plant, is the NAVSEA team's home turf, not an autonomy-data engine's.
5. **The neutral onboard trust layer.** Every onboard algorithm (DECK-fed, Fathom5's ERM, a prime's) needs to be trustable on the hull. DECK is one data source; it is not the layer they all emit into to be trusted.

---

## §6 — The blue ocean, defined (Blue Ocean four-actions)

Using the Blue Ocean Strategy grid to make the uncontested space explicit:

| Action | THESEUS move |
|---|---|
| **ELIMINATE** | Competing on raw detection accuracy (Windward owns it); competing with DECK on data collection/bandwidth (DECK owns it); building a bespoke ML stack (commodity, `INTEGRATION_SPEC.md`). |
| **REDUCE** | Custom-built components down to thin glue (adopt PyOD/Stone Soup/Zenoh/MLflow/Sigstore/OSCAL). Detector novelty as a selling point. |
| **RAISE** | Onboard autonomy *under DDIL* (keep reasoning when the link is cut); trust + accreditation (the record as the AO's evidence); human-in-command provability. |
| **CREATE** | **Provenance-gated fleet learning** (the safe Tesla-for-the-fleet loop); **cATO-for-AI** (accredit the learning pipeline, not frozen weights); the **onboard closed loop** that consumes DECK's curated data and closes it; the **neutral onboard trust layer** every algorithm emits into. |

**The uncontested intersection:** onboard-DDIL closed loop × provenance/accreditation record × provenance-gated fleet-merge × HM&E engineering domain. It is empty precisely because filling it requires a NAVSEA/NIWC team (domain + feeds + AO relationship) that a Silicon Valley autonomy-data company does not have. The barrier that keeps the ocean blue is the same barrier the team already cleared by existing.

---

## §7 — Complementary, not competitive (how THESEUS rides DECK)

The winning posture is **ride DECK, do not fight it**. Concretely:

- **DECK is the data engine; THESEUS is the trust + closed-loop layer that consumes its curated data.** DECK triages and delivers; THESEUS learns onboard, recommends to the watch, seals the decision, and makes the result fleet-mergeable + accreditable.
- **DECK gets data to where models are built; THESEUS makes the resulting model fieldable** (provenance record → cATO evidence the AO signs).
- **The pitch line:** *"DECK turns the ship into a data pipeline. THESEUS turns that pipeline into a closed, accreditable learning loop the fleet can trust under DDIL. DECK feeds the loop; we close it and prove it."*
- This is the same "be the payload, not the pipe" pattern as the UDS Fleet composition (`INTEGRATION_SPEC.md §5`): plug into the Warfighting Data Ecosystem as the trust + learning layer, not a rival data engine.

---

## §8 — The capture path (actionable)

1. **PAE RAS Industry Day (June 2026)** + the forthcoming **roadmap-to-industry**: the open door into the autonomy/data portfolio DECK sits in. The NAVSEA team is adjacent; use them to read the roadmap and position THESEUS as the trust/closed-loop layer.
2. **NV063 SBIR (opens 6/24)** remains the near-term non-dilutive wedge, and it maps to the onboard anomaly + explainable-alert + cold-start part of the loop.
3. **The accreditation relationship** is the long pole and the moat: an AO/PEO who accepts the provenance record as cATO-for-AI evidence. The team is the path.
4. **Partner surface with Applied Intuition** (later): THESEUS as the onboard trust/accreditation layer that DECK-curated models flow through, rather than a competitor. Worth a relationship once the wedge is proven.

---

## §9 — Demo/pitch implication (say it in the room)

- Lead with the loop DECK opens and nobody closes: "the Navy is collecting the data (DECK); we close the loop onboard and make it accreditable."
- Show the §6 miniature from the fleet-learning doc: 2 Pis as ships, the fleet brain, the provenance-gated merge that **rejects a poisoned delta live**, eval-gate, rollback, sealed record.
- Frame the HM&E engineering-plant focus as the team's home turf and DECK's blind spot.
- Hold the language discipline (`FLEET_LEARNING_VISION.md §8`): recommended-intervention/human-in-command; no "autonomous"; SWAN-side only.

---

## §10 — Honest caveats & open questions

- **DECK internals are not fully public.** Capabilities here are from consistent secondary coverage, not the verbatim release or a spec. Confirm against the DefenseScoop/FedTech primaries + any PAE RAS roadmap doc before external use.
- **Applied Intuition could extend.** A funded autonomy leader with a CDAO deal is a real long-term competitive risk if it moves toward trust/accreditation. Mitigation: own the NAVSEA-domain + accreditation-relationship part that is hardest for them to reach.
- **"Blue ocean" ≠ "easy."** The space is uncontested because it is hard (domain + DDIL + accreditation). That is the point, and it is why the team matters more than the tech.
- **Open verification:** the PAE RAS roadmap-to-industry contents; whether the Warfighting Data Ecosystem has a named trust/accreditation layer already (if so, integrate; if not, that is the open lane); UDS Fleet per-node model/attestation transport (`INTEGRATION_SPEC.md §5`).

---

## §11 — Sources (web-surfaced Jun 17 2026; titles/venues/dates confirmed)

- **DECK:** DefenseScoop "Navy program turns ships into continuous data pipelines for AI" (2026-03-19); FedTech "WEST 2026: DECK Will Turn Navy Ships Into 'Learning Systems'" (2026-02-16); TheDefensePost "Navy's New AI Data Engine Turns Ships Into Self-Learning [Systems]" (2026-03-23); hstoday (2026-03-24); techbytes "Navy DECK: Applied Intuition & Continuous AI Pipelines" (2026-03-19); Applied Intuition / PRNewswire "Delivers Flagship Data Engine Program" (2026-03-19).
- **PAE RAS:** Naval Sub League "New Navy Unmanned Acquisition Office Could Oversee up to 66 Programs" (2025-12-10); usvhub PAE RAS profile; Breaking Defense "Navy unveils acquisition reform, establishes five more PAEs" (2026-03-17); DefenseScoop "Navy PAE for robotic and autonomous systems preparing to release [roadmap]" (2026-04-22); sam.gov "PAE RAS June 2026 Industry Day" (2026-05-21).
- **Applied Intuition roadmap:** appliedintuitiondefense.com (Acuity, Axion); appliedintuition.com/blog "Axion and Acuity" (2025-05-20), "2025 Year in Review" (2025-12-19); PRNewswire "Department of War Selects Applied Intuition to Build Enterprise [capability]" (2026-05-14).
- **Navy data ecosystem:** Breaking Defense "ISV 2.0 / data fluent" (2024-08, upd. 2025-09); DefenseScoop "A first look at GenAI.mil" (2026-01-12); Federal News Network "Navy unites data in nerve centers" (2025-04-30); NAVSEA/DVIDS "Navy Leaders Emphasize Speed and a Unified Digital Ecosystem" (2026-05); USNI Proceedings "Warfighting Advantage: ... continuous learning" (2026-01).
