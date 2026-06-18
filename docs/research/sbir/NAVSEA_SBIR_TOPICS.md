# NAVSEA SBIR/BAA topics — Theseus fit review
*Captured Jun 17 2026. DON SBIR 26.2 (R2) / 26.3 (R3), "BZ" topics. Deep SOTA per topic is being compiled by a research pass — this is the capture + fit verdict. Submission path: DSIP/BAAT.*

## Headline: NV063 is the bullseye for Theseus
**DON26BZ03-NV063 — Anomalous Behavior Detection & Alerting for Congested Maritime Environments** is almost a spec for the Theseus ship-brain.

| Field | Detail |
|---|---|
| Command / Release | NAVSEA · Release 3 |
| Window | **Opens 6/24/26 · Closes 7/22/26** |
| CTA / Priority | Applied AI · Human-Machine Interfaces, Trusted AI & Autonomy |
| Wants | Automated **Pattern-of-Life (PoL)** of surface + air contacts around Navy ships — **AIS + ADS-B + radar fusion**, **explainable-AI** alerting, integrated with **Ship Self-Defense System (SSDS)** |
| Key constraints | **No large historical DB required**; must work in **novel OPAREAs**; Phase III = **live SSDS combat-system integration** |
| **Theseus fit** | **STRONG — pursue.** This *is* the situational-awareness organ of the ship brain: fuse the ship's sensor feeds, learn "normal" on the fly (no historical DB — matches our "learn the ship's normal" + DDIL design), flag the anomaly, explain it, human commands. Explainable AI + the tamper-evident record = "trusted AI/autonomy" in their words. A runtime-autonomy + zero-trust contact-intent-verification angle complements this. |

## The two that pair with NV063 (combat-system track lane)
**DON26BZ03-NV061 — Predictive Movement for Object-Oriented Tracking** · NAVSEA R3 · opens 6/24, closes 7/22
- ML-driven trajectory/kinematic prediction for **combat-system track management**.
- **Theseus fit: STRONG-adjacent.** Object-level prediction feeds the same track picture NV063 reasons over. NV061 (where is the track going) + NV063 (is the track behaving anomalously) = one coherent "object-level situational awareness" story. Pursue as a pair.

**DON26BZ03-NV065 — Adaptive Sensor Management** · NAVSEA R3 · opens 6/24, closes 7/22
- Dynamic tasking / resource allocation across **multi-sensor naval systems under adversarial conditions**.
- **Theseus fit: MEDIUM-STRONG.** The autonomy layer that decides *which sensor looks where* — the action side of the brain, relevant to denied-environment PNT/SA. Natural Phase-II extension once NV063/NV061 prove the SA picture.

## The two undersea topics (lower fit, note deadlines)
**DON26BZ02-NV050 — Low-Cost Bottoming Seabed Nodes for UUV Support** · NAVSEA R2 · **Closes 6/24/26 (≈1 week — likely too tight)**
- Seabed PNT / comms-relay nodes for UUV nav in **GPS-denied undersea**.
- **Theseus fit: WEAK/ADJACENT.** Hardware-infra play (seabed nodes), off our software-brain core. The *concept* (PNT when cut off) rhymes with DDIL, but it's a different build. Skip unless a hardware partner shows up; deadline is nearly gone.

**DON26BZ02-NV048 — Deep-Sea Object Detection & Localization for Towed MCM Sonar** · NAVSEA R2 · Closes 6/24/26
- ML mine-countermeasures sonar object localization undersea.
- **Theseus fit: WEAK.** Sonar/MCM-specific perception; our correlation/anomaly engine could in principle ingest sonar tracks, but it's a domain detour from the surface-ship brain. Skip for now.

---

## Recommendation
- **Pursue NV063 as the anchor** (strongest fit, R3 window 6/24–7/22, and it's exactly what we're building at Warhacker — the witnessed run becomes the SBIR proof).
- **Bundle NV061** (predictive track) as the paired object-SA story; **NV065** (adaptive sensor mgmt) as the Phase-II autonomy extension.
- **Skip NV050 / NV048** (undersea hardware/sonar — off-core, near-dead deadlines) unless a partner appears.
- **Why this matters:** Warhacker (Theseus demo, Jun 16–19) → NV063 opens **6/24, two days after the event** → the Warhacker build is a running head-start on a NAVSEA SBIR. The team (NAVSEA + retired Navy/Marine engineers) is the exact bidder profile.

## Honest rails (carry into any NV063 pitch)
- Human-in-command on any alert/action; explainable AI is *required* by the topic and is our strength (the tamper-evident record + the explanation).
- "No large historical DB / novel OPAREAs" = our on-the-fly "learn the ship's normal" approach, not a pretrained-on-everything claim.
- SSDS integration is **Phase III** — don't promise live combat-system integration in Phase I; scope to the SA/alerting layer that *feeds* SSDS.

---

# SOTA + mechanics (research pass, Jun 17 — sourced)

## SBIR mechanics (BZ03 = our window)
- **BZ03 (NV061/063/065):** pre-release Jun 3–23 (**TPOC Q&A closes Jun 23**), **opens Jun 24, closes Jul 22 2026**. BZ02 (NV048/050) **closes Jun 24** — too late + off-thesis, skip.
- **Phase I ≈ $315K** (up from the legacy $240K — the S.3971 reauthorization signed Apr 13 2026 raised caps; authorizes SBIR through FY2031). Phase II ≈ $1.5–2.15M / 24mo. Phase III = no SBIR funds but **sole-source authority**.
- **Eligibility:** for-profit, US, ≤500 employees, >50% US-owned. **NEW 2026: mandatory foreign-risk screening on every submission** (ownership/patents/personnel vs UFLPA, NS-CMIC, §889) — assemble docs now.
- **Submit via DSIP** (dodsbirsttr.mil). Need SAM UEI + **SBA SBC Control ID** + login.gov (sequential, slow — confirm Force AI already has these). **Phase I ≤15 pages.**
- **Biggest lever on the ~18% Navy accept rate: engage the TPOC during pre-release (by Jun 23)** — ask questions on the DSIP Q&A page, attend the webinar.
- **D2P2 (Direct-to-Phase-II)** may apply on a future cycle given our existing (non-SBIR-funded) edge-fusion stack.

## The combat-system reality (how a small vendor actually gets on)
- **SSDS** = Raytheon combat-management for **non-Aegis** ships (CVN, LHA/LHD, LPD); fuses radar/EO-IR/datalinks, automates self-defense w/ human override. NV063's Phase III target.
- **Aegis** (Lockheed) = DDG/CG; now **virtualized** (containers on generic servers, since USS Winston Churchill Dec 2023).
- **Integrated Combat System (ICS):** Navy consolidating SSDS+Aegis onto one Common Source Library; **first baseline delivered May 2026** via Lockheed's "Forge" CI/CD → **6-month update cadence**. *Strategic signal: the Navy is moving combat systems to containerized microservices + DevOps pacing — exactly our deploy model.*
- **Three realistic integration paths (do NOT embed in the kill chain in Phase I):** (1) **alongside, reading certified data pipes** in a separate container — the Maven/Palantir model; (2) **episodic data → train ashore → push models back** — the DECK/Applied Intuition model; (3) subcontract a prime (Lockheed/RTX/BAE) — slow (3–5yr), NAVSEA cert + Wallops Island testing + RMF. **NV063 Phase III = path #1.**
- **Latency budget (NV063 Phase III):** ML inference must return **<5s** (radar scan ~10s + fusion ~5s), total alert <~30s, on edge GPU/FPGA within ship power/thermal. Design for it from Phase I.
- **Standards to name:** MOSA (tri-service directive), SOSA, FACE/HOST. **Programs to track:** Project Overmatch, CANES (our data backbone), NIWC Atlantic/Pacific (the edge gate), PEO IWS (combat-system acquisition owner — engage via prime/SBIR).

## NV063 SOTA + the winning architecture (lead bid)
- **Methods:** unsupervised DL on AIS trajectories (autoencoders, WGAN-GP), **Graph Attention Networks**, DBSCAN→LSTM hybrids, and **AIS-LLM (Aug 2025)** — joint trajectory prediction + anomaly detection + **natural-language explanations** (directly answers the XAI requirement). Benchmarks: OMTAD, NATO STO/CMRE real-time AIS.
- **Fusion (AIS+ADS-B+radar):** EKF+IMM track-to-track, particle-filter+JPDA for dense targets, fuzzy fusion for spoofed/conflicting reports. Open gap: AIS↔radar coregistration under sensor mismatch in novel areas = **our wedge**.
- **The hard requirement = "no historical DB / novel OPAREA" (the differentiator).** Winning architecture to propose, staged:
  1. **Physics-Informed NN** (vessel kinematics) → works day-1 with ~10–20 tracks, no baseline
  2. **Few-shot / LLM transfer** from global AIS → week-1
  3. **Synthetic augmentation** (COLREG sims, CycleGAN AIS) → weeks 1–4
  This beats Windward/commercial players who assume weeks-to-months of data accumulation.
- **XAI:** SHAP/LIME + symbolic-neural + **atomic natural-language alerts** (why + recommended action, 1–2 sentences for a <10s operator decision). Precedent: AnoMili (explainable AD on the military 1553 bus).
- **Competitive whitespace:** Windward (behavioral maritime AI), HawkEye 360 (RF/dark vessels), Spire/Kpler (AIS), Anduril+Saronic (autonomy/MDA). **No vendor publicly owns "anomaly detection → SSDS alerting." Genuine whitespace.**

## NV061 SOTA (companion bid)
- For the **Maritime Targeting Cell (MTC)**: automate object tracking/prioritization + **predictive forecasting**. Transformers (HPNet, Trajectory Mamba) now beat LSTM; maritime PINN/LLM forecasters (SEMINT, FLP-XR); IMM-Kalman baseline; track mgmt via MHT/JPDA + GM-PHD; transformer data-association (DeepAF).
- **Wedge:** adversarial robustness (spoofed tracks spike error >150%), **calibrated uncertainty** (conformal prediction — combat systems need intervals, not point estimates), **<100ms edge inference**. Reuses the NV063 fusion + edge stack — low marginal cost to bid both.

## This-week actions
1. **Commit NV063 (lead) + NV061 (companion)** — both BZ03, close 7/22, shared stack.
2. **Engage the TPOCs by Jun 23** (pre-release Q&A) — highest single lever on acceptance.
3. **Confirm/finish registrations** (SAM UEI, SBA SBC Control ID, login.gov) + **foreign-risk screening docs**.
4. **NV063 technical volume:** lead with the cold-start architecture (PINN + few-shot/LLM + synthetic) + atomic XAI alerts; Phase III = alongside-SSDS via certified data pipes (Maven/DECK precedent), not embedded.

*Confidence: dates, topic existence, and the ~$315K Phase I are multi-source confirmed; exact base/option split + full topic text pull from DSIP at open (Jun 24). "BZ" nomenclature inferred. SSDS latency/cert specifics are press estimates.*
