# THESEUS — Integration Spec (Buy / Borrow / Build)

*The architecture decision: compose best-of-breed open components, keep our build to the thin glue plus the one thing only a NAVSEA/NIWC team can do. Web-grounded Jun 17 2026. Companion to `ROADMAP.md` (state) and `docs/WARHACKER_JUDGE_AUDIT.md` (scoring). Drafted by the THESEUS lane.*

> **Why this exists.** The record, the detection, the deploy, and the machinery CBM are all commoditizing (`WARHACKER_JUDGE_AUDIT.md §0.1`; Glacis/nono/cachee on receipts, Windward on detection, Defense Unicorns on deploy, Fathom5 ERM on CBM). Re-deriving any of them burns the team's only scarce asset: Navy domain access. So we adopt standards everywhere and build only the non-commodity inch. Adopting the standards is itself the moat-sharpener: a recognized, interoperable record is what makes other vendors emit into it.

---

## §1 — The GATE (every adopted component must pass all three)

1. **License:** permissive / commercial-OK (we ship a product + a for-profit SBIR). GPL only as a standalone sidecar process consumed over a socket, never static-linked.
2. **Airgap-capable:** runs fully disconnected on-prem. No mandatory cloud call. (This is what disqualified Windward: cloud SaaS cannot reach a ship at sea.)
3. **Edge-feasible** for the onboard tier (fits a 4GB Pi / CPU), **or** explicitly shore-tier only (Ryzen/Blackwell stand-in) and labeled as such.

A component that fails any one is a reference/benchmark or a future partner, not an input.

---

## §2 — Buy / Borrow / Build map

| Layer | ADOPT (borrow) | License | Airgap / edge fit | What THESEUS builds on top |
|---|---|---|---|---|
| **Detection** — machinery CBM + AIS Pattern-of-Life | **PyOD** (60+ detectors, benchmarked) · **Merlion** (TS anomaly + forecast/RUL) · **River** / **StreamAD** (online cold-start streaming) | BSD / BSD / BSD / Apache* | Pure-Python, CPU, edge-OK | Wrap our autoencoder *inside* PyOD orchestration so the NV063 number is benchmarked vs 60 detectors, not bespoke. River/StreamAD = the true "no historical DB" cold-start path. |
| **Fusion / tracking** — the cross-system differentiator engine | **Stone Soup** (DSTL / UK MoD) | MIT | Python, edge-OK | The onboard *cross-system* fuse (machinery + contacts + power + nav → one ship-state). Stone Soup gives track-to-track fusion (Covariance Intersection) + AIS/radar/ADS-B; we supply the multi-organ orchestration under DDIL. Do **not** build a tracker. |
| **DDIL transport + ship-bus bridge** | **Eclipse Zenoh** + **zenoh-plugin-dds** | dual EPL-2.0 / **Apache-2.0** (elect Apache) | Rust, built for intermittent/constrained links | The DDS plugin reads the **SWAN-side DDS bus the Navy already runs** AND gives DDIL geo-routing. Two problems, one adopt. We build the per-subsystem adapter → canonical `Observation` schema. |
| **Partition-tolerant shared state** | **automerge** (CRDT) | MIT/Apache | Rust/edge-OK | Merges on reconnect, no consensus round-trip. We define the ship-state document shape. |
| **The record — EXTERNAL format (the moat)** | **in-toto** attestations + **SLSA** provenance + **Sigstore/cosign** | Apache / OpenSSF | offline key-based signing works airgapped | **Stop shipping a bespoke hash chain as the external artifact.** Emit standard attestations DoD supply-chain already mandates. We build the *runtime-decision extension* (seal a human decision / model-promotion as an in-toto-style attestation). Internal Merkle chain stays as an implementation detail. |
| **Accreditation evidence** | **OSCAL** (NIST) via **Lula** (Defense Unicorns) | public domain / Apache | local CLI, airgap-OK | Emit the record as **OSCAL assessment-results** so it drops into the AO's workflow. We build the THESEUS-event → OSCAL CA-7/AU-9 mapping. (Optional: IBM Trestle, the Continuous Compliance Framework.) |
| **Model lifecycle** | **MLflow** (registry/tracking, shore tier) + **ONNX Runtime** (edge inference) | Apache / MIT | MLflow = shore; ONNX = 4GB-Pi edge (have it: ~115KB, sub-ms) | The **DDIL delivery loop** (signed bundle → promote → rollback → seal → sync-on-reconnect) riding UDS Tactical Edge. Skip KServe/Seldon/BentoML (GPU-cloud-heavy, no DDIL). |
| **Deploy / admission / supply-chain** | **UDS Core** + **Zarf** + **Pepr** + **Syft** (SBOM) + **cosign** | Apache | airgap-native (DU's whole thesis) | Already adopted + verified (`deploy/UDS_DEPLOY_EVIDENCE.md`). We build the Pepr rails (human-in-command, no-egress, append-only) + the bundle. |
| **Explainer** | **llama.cpp** + **Qwen2.5-1.5B** | MIT / Apache-2.0 | runs on Pi-class, airgapped | We build the deterministic-finding → grounded-NL-alert seam, fail-loud if no LLM. (Avoid Gemma for the shippable path: Gemma license has use-restrictions — see §6.) |
| **Ingest / capture** | **pyais** (decode) + **AIS-catcher** / **dump1090-fa** (SDR) | MIT / GPL-sidecar | RX-only, legal, airgapped | The own-capture rig (real AIS/ADS-B, no cloud). GPL tools run as sidecar processes only. |

\* StreamAD license to confirm (§6).

---

## §3 — What THESEUS actually builds (the ~15% non-commodity)

After maximal borrowing, the build surface collapses to four things nobody packages and only this team can do:

1. **Onboard cross-system fusion under DDIL** — fuse the borrowed organs into one ship-state. No single library does multi-subsystem onboard fusion; this is the "cognitive layer" north star, scoped to SWAN-side, two organs (machinery + contacts) in v1.
2. **The runtime-decision attestation extension** — the genuinely novel inch. Supply-chain tooling attests *build time*; we extend in-toto/OSCAL to attest *runtime decisions onboard* (a sealed human accept/override, a model promotion/rollback). This is what no incumbent does.
3. **The DDIL model-delivery loop** — promote/rollback/seal/sync-on-reconnect, riding UDS Tactical Edge, surfacing to UDS Fleet on reconnect.
4. **Navy domain knowledge** — per-hull "normal," reachable feeds past the primes, the AO relationship. Not code. The team. The whole reason the niche is empty.

---

## §4 — The record reframe (the key strategic shift)

**Before:** "We built a tamper-evident hash chain." A commodity a prime clones in a sprint; a shelf of 2026 startups already shipped it.

**After:** "We emit **SLSA / in-toto / Sigstore** attestations and **NIST OSCAL** assessment-results, for **runtime AI decisions, onboard, under DDIL**, fused with the **UK MoD's Stone Soup**, transported over **Eclipse Zenoh's DDS bridge** into the ship's own bus, deployed on **UDS**."

That is a systems-integration story a prime cannot wave away and an AO recognizes on sight. The standards are the moat-sharpener: a recognized, interoperable record is precisely what makes *other vendors* (Fathom5, a prime, even a maritime detector) emit into it to be trusted onboard. We adopt the standard DoD already trusts and extend it to runtime; we do not invent a standard nobody has seen.

---

## §5 — Composition with Defense Unicorns (partner, not competitor)

- **UDS Tactical Edge** = the productized version of our model-delivery loop (airgap one-click updates). THESEUS packages as the UDS bundle Tactical Edge delivers.
- **UDS Fleet** (launched Jun 2 2026) = fleet-wide visibility/control across distributed systems. THESEUS is the **onboard payload that makes Fleet worth putting on a ship**: Fleet is the shore/squadron pane; THESEUS runs on each hull under DDIL and pushes its state + sealed OSCAL record up to Fleet on reconnect. Clean composition, no overlap.
- **Verify before lock:** does UDS Fleet expose (a) a way to register a managed application/tenant, and (b) ingestion of a per-node attestation/record? (30-min research task; open.)

---

## §6 — License-verification checklist (pre-lock gate; honest)

Most are well-known permissive; the few flags below must be confirmed before any production lock (LICENSE-FIRST discipline, same as the datasets pass):

- ✅ High confidence permissive: Stone Soup (MIT), PyOD (BSD-2), Merlion (BSD-3), River (BSD-3), MLflow (Apache-2.0), ONNX Runtime (MIT), in-toto/cosign/Sigstore (Apache-2.0), Lula (Apache-2.0), OSCAL (US-Gov public domain), automerge (MIT/Apache), pyais (MIT), llama.cpp (MIT), Qwen2.5-1.5B (Apache-2.0).
- ⚠️ **Verify before lock:** **Zenoh** — dual EPL-2.0/Apache-2.0; elect **Apache-2.0** and document the election (EPL is file-level weak-copyleft if you modify Zenoh source). **StreamAD** — confirm Apache vs other. **Gemma** — Gemma license carries use-restrictions; **exclude from the shippable path**, prefer Qwen2.5 (Apache-2.0). **AIS-catcher / dump1090-fa** — GPL; **sidecar process only**, never static-linked.
- SLSA is a spec (CC-BY), not code; no embedding concern.

---

## §7 — Sequencing (do not destabilize the Warhacker demo)

The demo stands as-is for Jun 16-19. This spec is primarily the **Phase-2 (SBIR build-out → Jul 22)** hardening architecture. Two adopts are low-risk and high-value enough to pull in early:

1. **Record reframe (format/doc level, low code risk):** describe the existing record as in-toto/OSCAL-aligned and have Lula emit the OSCAL assessment-results. Lifts Death Proof + Judges Pick immediately, mostly documentation.
2. **PyOD benchmark wrap:** run the autoencoder inside PyOD's orchestration to produce a benchmarked NV063 number. Strengthens the eval honesty with little risk.

Defer to Phase 2 (heavier, post-event): Zenoh/DDS bridge, automerge CRDT state, Stone Soup fusion, MLflow↔ONNX DDIL loop hardening, UDS Fleet tenant registration.

---

## §8 — Effect on the rubric

- **Portability (25%):** standards travel; UDS Fleet/Tactical composition = real cloud-to-edge. ↑
- **Death Proof (25%):** OSCAL is the AO's own language; in-toto/SLSA/cosign are the supply-chain evidence the ATO wants. ↑↑ (still gated on the sponsor sentence — the non-code long pole).
- **Most Resourceful (15%):** "we composed best-of-breed and built only the Navy-specific inch" is the resourceful story. ↑
- **Judges Pick (10%):** DU engineers see Lula + Zenoh + Sigstore + Stone Soup and know it's the real thing, not slideware. ↑
- Build surface cut ~80%, freeing the team for the fusion glue + the accreditation positioning.

---

## §9 — Honest risks

- **Partner-overlap risk:** UDS Fleet/Tactical Edge climb toward our model-delivery objectives. Mitigation: build the *DDIL runtime loop + the onboard record*, not the delivery transport (that's DU's). Be the payload, not the pipe.
- **Standard ≠ adoption:** emitting OSCAL/in-toto does not by itself make an AO accept the record as evidence. The sponsor conversation is still the gate (kill-criterion in `WARHACKER_JUDGE_AUDIT.md §0.1`).
- **Integration tax:** composing eight projects has its own glue + version-pinning + airgap-bundling cost. The ~80% build cut is real, but the integration/packaging effort is not zero; budget it in Phase 2.
- **License drift:** pin versions; re-run §6 before any production lock.
