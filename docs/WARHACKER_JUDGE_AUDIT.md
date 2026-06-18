# THESEUS — Warhacker Judge Audit + "Over-the-Top" Plan

*Adversarial full-stack audit, written as a hostile Warhacker judge (Defense Unicorns + CDAO engineers in the room). Scored against the official rubric. Every finding traces to a file or a verified source. Drafted by the THESEUS lane (audit only); fixes are tagged by owning lane. Jun 17 2026.*

> **How to read this:** §0 the rubric VERBATIM + the current (Jun 17 day-1-close) re-score, which **supersedes** the original §2 scorecard. §1–§8 are the original pass, kept for delta tracking.

---

## §0 — The rubric, VERBATIM (source of truth)

> Copied verbatim from the Warhacker judging-criteria page (founder-supplied Jun 17 2026). Do not paraphrase; reference this block.

```
Judging Criteria
Understand how your project will be evaluated

5 Criteria · 50 pts Max Score

Weight Distribution
  Mission Impact     25%
  Portability        25%
  Death Proof        25%
  Most Resourceful   15%
  Judges Pick        10%

1. Mission Impact   — 25% weight — 0–10 pts — Required
   How significant is the problem for the target mission?

2. Portability      — 25% weight — 0–10 pts — Required
   How ready is the capability to be deployed wherever the mission requires?

3. Death Proof      — 25% weight — 0–10 pts — Required
   How ready is the capability to cross the valley of death into sustained operations?

4. Most Resourceful — 15% weight — 0–10 pts — Required
   How effective was the team to overcome challenges?

5. Judges Pick      — 10% weight — 0–10 pts — Required
   The Warhacker judges bring expertise and unique perspective; their feedback
   will be invaluable to building effective solutions.
```

---

## §0.1 — CURRENT re-score (Jun 17, day-1 close) — supersedes §2

*Fresh judge pass against verified artifacts (git log + `deploy/UDS_DEPLOY_EVIDENCE.md` + a live `pytest`/`make smoke` run). Every score traces to a receipt.*

| Dimension | Wt | **Now** | Prior | Δ | Why a hostile judge lands here (receipts) |
|---|---|---|---|---|---|
| **Mission Impact** | 25% | **7.0** | 6.5 | +0.5 | The differentiated story is now the hero, not buried: tamper-evident **record-as-accreditation-substrate** + **sealed human decision** + DDIL, demoed first; machinery CBM demoted off ERM's turf. Maps to a real opening SBIR (NV063, 6/24). Ceiling-capped because it's decision-support analytics (ERM already fields machinery monitoring) and the "be-the-substrate" category is a claim, not yet adoption. |
| **Portability** | 25% | **7.0** | 4.5 | **+2.5** | Real DU tooling, verified in-cluster: hardened `theseus-edge:0.1.0` **airgap side-loaded** (`k3d image import`, `imagePullPolicy:Never`), in-cluster Job **Completed 7s + offline verify PASS**, real **Zarf signed pkg + SBOM (Syft, 100 pkgs)**, real **cosign** sign/verify (tampered bytes rejected), **ONNX edge path** (~115KB, sub-ms, fits 4GB Pi), shore→ship delivery 11/11 PASS, **airgap-clean frontend** (zero CDN). Capped: full **uds-core platform** (Istio/Keycloak/Falco/UDS Operator) did NOT deploy (GHCR rate-limit; `Package` CR inert) and multi-node Pi failover not yet live. |
| **Death Proof** | 25% | **5.5** | 3.5 | **+2.0** | Real death-proof artifacts now exist: **SBOM** (the ATO supply-chain doc), **cosign signature + negative control**, **Pepr admission** enforcing AC-6/SC-7/AU-9 at admission (4 DENY / 2 ADMIT, human-in-command required), the record as reusable accreditation evidence. Still the lowest and the #1 lever: **no program-office sponsor / AO sentence** (the actual valley of death — the demo script admits it), Lula still 2/8 unexercised this pass, uds-core ATO-inheritance documented-not-demonstrated, no Rekor. |
| **Most Resourceful** | 15% | **8.5** | 8.0 | +0.5 | Standout. Multi-tier real HW; MLflow containerized around a Py3.14 break; SOTA reproduced on MPS; **honest self-correction** (MetroPT leakage caught, SOG-1023 bug caught+fixed `ais_pol.py:97`, OMTAD rejected, self-scrubbed own banned headline); DU tooling stood up under GHCR throttle with honest fallback; ONNX parity 6e-08; 9-person pickup team integrated. |
| **Judges Pick** | 10% | **7.5** | 6.5 | +1.0 | The self-inflicted wound is gone (banned "self-controlled ship brain" headline scrubbed). What's left is catnip for DU/CDAO engineers: live **tamper-snap**, **Pepr DENY** on stage, the **sealed human decision**, instrument-grade CIC, and a relentless **REAL-vs-PENDING honesty** posture that reads as credibility, not spin. |

**Weighted total ≈ 6.9 / 10  (~34.5 / 50)** — up from ~5.4 prior. Math: 7.0(.25)+7.0(.25)+5.5(.25)+8.5(.15)+7.5(.10) = 1.75+1.75+1.375+1.275+0.75.

**Prior kill-shots — disposition:** #2 decision-theater → **CLOSED** (`POST /api/decision` seals a `human_decision` leaf, verify PASS). #3 frontend wrong-port/CDN → **CLOSED** (defaults to real `:8501`, zero CDN, wired to decision-seal). #6 banned headline → **CLOSED** (scrubbed). #1 UDS deploy → **PARTIAL** (real Zarf+Pepr+cosign+SBOM in-cluster; full uds-core platform pending rate-limit). #7 autoencoder LOFO → **CLOSED** in `MODEL_BENCHMARKS.md` (AUC 0.939 LOFO). #8 explainer real-LLM seal → **OPEN** (`serve/explain_local.py` WIP, untracked).

**The 3 highest-leverage moves left (all in the 25% lanes):**
1. **Land one attributed AO/PEO sentence** that the verifiable record counts as accreditation evidence → Death Proof 5.5→7+. The single biggest unlock; it's relationship work, not code.
2. **Deploy on full uds-core** (registry-mirrored host to dodge the GHCR throttle) → show Istio mTLS + default-deny NetworkPolicy + Keycloak + the `Package` CR reconciling → Portability 7→8.5 and Death Proof up.
3. **Capture the 60s live-demo recording + multi-node Pi failover** (Day 2) → de-risks the live run and turns "edge" into a real cloud-to-edge beat → Portability + Judges Pick.

**Staleness flag:** `eval/out/curated_metrics.json` (precision 0.36) was scored **before** the SOG-1023 fix landed; re-run the curated eval post-fix for an honest, improved NV063 number before any external use.

---

## §1 — The official rubric (weights)

| # | Dimension | Weight | The question |
|---|---|---|---|
| 1 | **Mission Impact** | **25%** | How significant is the problem for the target mission? |
| 2 | **Portability** | **25%** | How ready is the capability to be deployed wherever the mission requires? |
| 3 | **Death Proof** | **25%** | How ready is the capability to **cross the valley of death into sustained operations**? |
| 4 | **Most Resourceful** | **15%** | How effective was the team at overcoming challenges? |
| 5 | **Judges Pick** | **10%** | Judges' expertise + unique perspective. |

Each scored 0–10. **75% of the score is problem-significance + deployability + crossing-the-valley-of-death.** The event motto is **BUILD → PACKAGE → DEPLOY**, "don't stop at prototype, shoot for prod," success measured by **apps deployed AND authorized in mission environments via UDS Core** (cloud-to-edge). "Death Proof" is the rubric's name for the exact thing our own Red Team called our #1 cause of death: no program sponsor + no ATO + no real feed = "a clean bundle that sits in a lab forever."

---

## §2 — Adversarial scorecard (where we land TODAY, unsharpened)

| Dimension | Wt | Score (adversarial) | Why a hostile judge lands there |
|---|---|---|---|
| Mission Impact | 25% | **6.5 / 10** | Real, named problem (onboard AI under DDIL; trust-to-field is the Navy's actual blocker). But the **hero demo leads with machinery CBM, which Fathom5 ERM already fields on USS Fitzgerald (DDG, Jan 2025) at ~10k readings/sec** — we open on the incumbent's turf. The differentiated impact (the *record* + cross-system DDIL fusion) is buried. |
| Portability | 25% | **4.5 / 10** | This is the event's home turf and we don't actually hold it: **the bundle does NOT deploy on UDS Core** (`deploy/uds/uds-bundle.yaml` has `core-slim-dev` commented out; the UDS `Package` CR is an unwired `[STUB]`). Nothing was built (`no deploy/uds/dist`, `no zarf/dist`). The flashy UIs **break airgapped** (React baked the wrong API port → ships MOCK + red "OFFLINE"; React pulls a CDN HDRI; Streamlit pulls CDN fonts + carto basemap). Single-node only. The airgap-clean `cic.html` saves it from a worse score. |
| **Death Proof** | 25% | **3.5 / 10** | **The weakest, and it's 25%.** Zero program sponsor / AO, zero ATO artifacts, **Lula = 2 of 8 controls live and both are trivial presence/regex checks** (AU-9 doesn't even re-hash the chain), no Iron Bank base, no signed SBOM, no cosign. "Inherit the ATO" with uds-core switched off is hand-waving. No false-alarm number on real labels. By our own Red Team this is the valley of death. |
| Most Resourceful | 15% | **8 / 10** | Genuinely strong: real multi-tier hardware (2× Pi 5 + Ryzen 32GB + Blackwell), MLflow containerized after working around a Python 3.14 break, SOTA reproduced on Apple MPS, **honest self-correction** (caught own MetroPT leakage F1 0.94→0.26, the SOG-sentinel bug, rejected OMTAD as unusable), a lot shipped in days, stdlib-only edge discipline. |
| Judges Pick | 10% | **6.5 / 10** | High ceiling (the live tamper-snap + Pepr machine-enforced rails + the honesty discipline are catnip for DU engineers) but **self-sabotaged**: the public README headline says "self-controlled ship brain," the exact phrase our own `BUILD_VISION.md` banned. |

**Weighted total as-is ≈ 5.4 / 10.** The two 25% dimensions where we're weakest (Portability 4.5, Death Proof 3.5) are *also the event's whole point* and are the highest-leverage fixes. Move those two to ~7.5 and the total jumps to ~7.0+.

---

## §3 — The kill-shots (questions that deflate the pitch)

1. **"`uds deploy` it on uds-core right now — show me Istio mTLS, default-deny egress, the Keycloak login."** Can't: core is commented out, the Package CR is an unwired stub, there's no UI Service to expose. The entire UDS value-add is off. *(Portability/Death Proof)*
2. **"Hit OVERRIDE on that spoof contact, now show me that decision as a new sealed leaf in the Merkle chain."** Can't: `demo/api.py` is GET-only (no `do_POST`); every UI keeps the human decision in local state. **The climactic "human decides → proven in the record" beat is theater.** *(Mission Impact/Judges Pick)*
3. **"Name the program office or AO who has agreed your record counts as accreditation evidence."** None. *(Death Proof — the literal valley of death)*
4. **"Fathom5 ERM already does your machinery demo on USS Fitzgerald. What do you do that ERM doesn't, and what stops ERM adding a hash chain next sprint?"** *(Mission Impact)*
5. **"Your AIS cell threw 1,029 alerts on 11,898 tracks with no ground-truth false-alarm rate. Trust on a ship is one-shot. Why would a watch officer turn this on?"** *(Mission Impact)*
6. **"Your README says 'self-controlled ship brain'; your own Red Team doc says never say that. Which Theseus am I funding?"** Self-inflicted. *(Judges Pick/credibility)*
7. **"Your headline ROC-AUC 0.978 uses the same non-LOFO split you discredited for the supervised model. Show me the leave-one-failure-out number."** *(Mission Impact/integrity)*
8. **"Your 'explainable AI' (NV063) — show me one sealed explained-alert. Is an LLM even running, or is that a template echoing the detector?"** On the demo box: template fallback, zero `explained_alert` leaves sealed. *(Mission Impact)*

---

## §4 — What is genuinely strong (do NOT break)

- **The tamper-evident record is the real moat and it actually works.** `referee/chain.py` SHA-256 + Merkle; a 1-byte flip snaps the chain at the named leaf, verified offline. This is the most differentiated, most credible artifact and no incumbent demos it.
- **The ML spine is ALL-REAL and reproduces.** CBM RMSE **0.00382** (reproduced; cross-checks the sealed registry 0.003823), Pi stdlib-OLS **0.00589** (reproduced), autoencoder ROC-AUC **0.978** (reproduced; held-out 0.985), NV061 reproduces published TrAISformer SOTA (0.48/0.90/1.48 nmi) and beats the constant-velocity floor ~13×.
- **HONESTY-FIRST is a competitive weapon in a CDAO/DU room.** Self-flagged leakage, disclosed sample sizes + base rates + baselines, OMTAD rejected, C-MAPSS labeled a "floor not SOTA." `docs/proposals/NV063/TECHNICAL_APPROACH.md` (BUILT/PARTIAL/PROPOSED) is the best doc in the repo.
- **The cold-start wedge** (no historical DB, in-situ envelope, novel OPAREA, ~4s on 1.5M real AIS rows, pure stdlib) is a genuine technical differentiator vs commercial PoL.
- **`cic.html` + `demo/api.py` is genuinely demo-grade and airgap-clean** (inline SVG/CSS/JS, zero CDN, real sealed record + real AIS). This is the hero surface.
- **The Pepr rails compile and are fail-closed** (`onError:reject`) — the seed of a machine-enforced safety case.

---

## §5 — The over-the-top plan (ranked by rubric leverage)

Lane key: **[FE]** frontend · **[DEPLOY]** deploy/UDS/Pepr/Lula · **[ML]** demo/models · **[DOCS]** narrative (THESEUS lane) · **[TEAM]** human/logistics. THESEUS owns docs/eval/models/ingest; the rest are WARHACKER/team lanes — flagged for action, not for me to edit.

### TIER 0 — before the outbrief (cheap, kills self-inflicted wounds)
| # | Action | Lane | Rubric |
|---|---|---|---|
| 0.1 | **Scrub "self-controlled ship brain" + "bounded autonomy" from every public surface** (`README.md:3`, `ROADMAP.md:4`, `docs/vision/PLAN.md:1/7`, `frontend/README.md:3`). One canonical headline everywhere: *"An airgapped, tamper-evident onboard decision-support substrate — human always in command."* Make the top of the repo match `BUILD_VISION.md`. | DOCS/FE | Judges Pick, credibility |
| 0.2 | **Seal the human decision live.** Add `do_POST /api/decision` to `demo/api.py` → append a `watch_decision` leaf (verdict + officer + ts) → re-verify. Wire `cic.html` ACCEPT/OVERRIDE to POST. On click the **leaf count ticks 54→55 on screen, RECORD re-verifies PASS**. ~30 lines; turns the moat from theater into the visceral payoff and closes beats 3→4. | FE/ML | Mission Impact, Judges Pick, Portability |
| 0.3 | **Make `cic.html` the hero; fix-or-hide the rest.** Demo `http://localhost:8077/`. If React is shown: rebuild with the correct `VITE_THESEUS_API` (it baked `localhost:8501` → MOCK + red OFFLINE) and self-host or drop the CDN night-HDRI. Don't demo Streamlit's map airgapped (CDN basemap dies). | FE | Portability, Judges Pick |
| 0.4 | **Pre-stage + demo-doctor preflight.** The 770MB AIS CSV + sealed record are gitignored → a fresh venue laptop is empty. Stage them; add a preflight that asserts data sha256 == sealed, record verifies, datasets present, (LLM reachable) before the live run. `demo/stage_data.py` can emit PLACEHOLDER offline — a preflight removes any on-stage silent degrade. | TEAM/ML | Portability, Death Proof |

### TIER 1 — move the three 25% dimensions (the score lives here)
| # | Action | Lane | Rubric |
|---|---|---|---|
| 1.1 | **Actually deploy on UDS Core and record it.** Uncomment `core-slim-dev` in `uds-bundle.yaml`, wire `uds-package.yaml` into a real `zarf.yaml` component, `uds deploy` on k3d, capture an asciinema of: Istio sidecar injected, default-deny NetworkPolicy applied, egress test failing closed, the Job green. **This is the single biggest unlock — the event's own platform.** | DEPLOY | **Portability 25%** + Death Proof 25% |
| 1.2 | **Produce Death-Proof artifacts on disk.** Rebuild on an Iron Bank base (`registry1.dso.mil/ironbank/...`), run `scripts/scan.sh` (install trivy) → commit the signed SBOM, `cosign sign` the bundle + `cosign verify` in an `onDeploy.before` action. Add a **one-page RAISE/eMASS control-inheritance matrix**: which 800-53 controls come from uds-core vs the Theseus delta. | DEPLOY | **Death Proof 25%** |
| 1.3 | **Get one attributed sentence from a NAVSEA/PEO/AO** that a verifiable replayable record is accreditation evidence they would accept. One sentence neutralizes the #3 kill-shot and the Red Team's #1 death cause. | TEAM | **Death Proof 25%** |
| 1.4 | **Re-cut the hero demo to the RECORD + cross-system DDIL fusion** (the one thing no incumbent demos): pull the cord → machinery + contacts organs disagree → fused ship-state → explainable recommend → human override (sealed, leaf ticks) → tamper-snap → restore. Lead with this, not gas-turbine RMSE (ERM's turf). | ML/FE/DOCS | **Mission Impact 25%** |
| 1.5 | **Ship a real false-alarm number** per-OPAREA at a watch-tolerable threshold (<~1 nuisance/watch). Grow the analyst-curated eval (`eval/curated_labels.csv`, n=50 today → more tracks + NAVSEA SME sign-off) and/or land a GFW commercial-use grant. A number beats a mechanism. | ML/DOCS | Mission Impact, Death Proof |

### TIER 2 — rigor + safety-case flex (cements Judges Pick + Death Proof)
| # | Action | Lane | Rubric |
|---|---|---|---|
| 2.1 | **Make Pepr human-in-command real + tested.** Label the actual workload (`theseus.forceos.ai/action: model-promote`), bind approval to a **sealed approval leaf** (verify the ref exists + chains, not just non-empty), ship `theseus-policies.test.ts` proving deny-on-missing-approval, and **live-reject a `kubectl apply`** on stage. "Our rails are machine-enforced, not slideware" is how you *survive* the safety review instead of fearing it. | DEPLOY | Death Proof, Judges Pick |
| 2.2 | **Re-headline the autoencoder on the leave-one-failure-out number (0.939) and SEAL it.** The 0.978 uses the exact non-LOFO protocol the repo discredited; the LOFO AUC (0.865/0.931/0.993/0.968, mean **0.939**) holds and degrades gracefully — turn kill-shot #7 into a flex. | ML | Mission Impact, integrity |
| 2.3 | **Make the explainer provably real + fail-loud.** Start/verify the local qwen2.5:1.5b endpoint in `run_full.sh`, seal `explained_alert` leaves with `explainer:<model>` provenance, **abort loudly** (not silent template) if no LLM. Then the moat covers the LLM step end-to-end. | ML | Mission Impact |
| 2.4 | **Lula: promote presence-checks to verification + raise coverage.** Have AU-9 invoke the real chain re-hash; add live validations for AC-6 (assert the deployed pod securityContext) and SC-7 (assert the NetworkPolicy). Retitle the component-definition for the model-loop, not just the Referee. | DEPLOY | Death Proof |
| 2.5 | **Multi-node Pi failover beat.** Loop as a Deployment behind a Service on the 2-Pi Tailscale mesh; kill node A, node B serves last-good + the record continues. Turns "edge" into the real cloud-to-edge story. | TEAM/DEPLOY | Portability |

### TIER 3 — visceral polish (Judges Pick)
| # | Action | Lane | Rubric |
|---|---|---|---|
| 3.1 | **Anchor the tactical plot geographically** (`ais_pol.py --box 25,31,-82,-79` Florida Straits + a faint coastline/OPAREA box) so contacts cluster meaningfully instead of reading as random dots across CONUS. | FE/ML | Judges Pick, Portability |
| 3.2 | **One-key TAMPER → live SNAP → restore** bound to a button (not a terminal command) so the board flashes red `CHAIN SNAP @ leaf N` then restores to PASS. Guaranteed gasp. | FE | Judges Pick |
| 3.3 | **De-ambiguate "offline":** amber **"DEMO FIXTURE"** chip vs an explicit **"DDIL / AIR-GAP"** posture chip. Never let air-gap-by-design look like a broken link. | FE | Judges Pick |
| 3.4 | **Reframe all three incumbents as channels** in one slide: Fathom5 ERM / Applied Intuition DECK / a prime's algorithm each *emitting into the Theseus record*. "We're the trust layer they plug into" converts competitive questions into partnership questions. | DOCS | Mission Impact |

---

## §6 — If you do only 6 things
1. **Scrub "self-controlled ship brain"** from public surfaces (Tier 0.1). [free, kills kill-shot #6]
2. **Seal the human decision live** so the leaf count ticks on ACCEPT/OVERRIDE (Tier 0.2). [the demo payoff]
3. **Actually `uds deploy` on UDS Core + record it** (Tier 1.1). [Portability + Death Proof, the event's platform]
4. **Iron Bank + signed SBOM + a RAISE control-inheritance one-pager** (Tier 1.2). [Death Proof artifacts]
5. **Re-cut the hero to the record + cross-system DDIL fusion**, not machinery CBM (Tier 1.4). [Mission Impact off ERM's turf]
6. **One attributed AO/PEO sentence** that the record is accreditation evidence (Tier 1.3). [the valley-of-death sentence]

---

## §7 — Integrity / OPSEC red flags (fix NOW, hackathon-enders)
- **🔴 Named government official as a procurement-steering teammate.** `docs/integration/DEFENSE_UNICORNS.md` states a NIWC Atlantic **Deputy Director is "on our team" steering the OTA toward us.** This is an **organizational-conflict-of-interest optic** and is unverified (appears on no team roster). **Verify or delete** — never say it in-room.
- **🔴 Real active-duty/government names + commands in artifacts**, against our own `docs/ONBOARDING.md` "roles not names in anything left behind." Compounded by a **public-vs-private repo contradiction** (`README`/`ROADMAP`/`KANBAN` say public AGPL; `PLAN.md` says private; the Jun 17 log says per-repo collaborators = private). If it is public, named engineers are exposed. **Resolve + strip names from public/left-behind docs.**
- **🟠 "Rides onto a ship" overstates the Apr 2026 Leidos+DU OTA**, which Breaking Defense describes as a *lab-based prototype trial*. Add the caveat or a judge corrects you.
- **🟠 Scrub "bounded autonomy"** (`PLAN.md`) — in a room whose rail is "never autonomous ship control," say "advisory decision-support; no autonomous actions exist by construction." Carry the "tamper-evident-not-proof / advisory-only" qualifier on every surface, not just the proposals.

---

## §8 — Sources (competitive, verified)
- Fathom5 ERM on USS Fitzgerald (first PoR AI on a warship, ~10k readings/sec): twz.com/news-features/destroyer-has-become-first-u-s-navy-ship-to-deploy-ai · fathom5.com
- Applied Intuition **DECK** (Navy data engine, delivered Mar 19 2026; onboard collection + operator overlays): appliedintuition.com/press-releases/applied-intuition-delivers-flagship-data-engine · defensescoop.com/2026/03/19/navy-deck-data-pipelines-ai-development
- Palantir **ShipOS** ($448M, Dec 2025; shipbuilding/supply-chain, not onboard-DDIL): news.usni.org/2025/12/09/navy-palantir-announce-448m-ship-os-ai-tool
- **UDS Core** (FOSS secure runtime; Istio mTLS, default-deny egress, Keycloak SSO, Pepr admission, auto-SBOM/compliance): github.com/defenseunicorns/uds-core · docs.defenseunicorns.com/core · repo1.dso.mil/platform-one/distros/defense-unicorns/uds-core
- Leidos + Defense Unicorns NIWC Atlantic OTA (Apr 2026, lab-based): breakingdefense.com/2026/04/navy-selects-leidos-defense-unicorns-to-test-software

*Audit method: read the full stack across all lanes (deploy/, demo/, models/, eval/, frontend/, referee/, docs/) via 4 parallel adversarial reads; reproduced the headline ML numbers; verified the tamper-snap; confirmed the uds-core/Pepr/Lula state by reading source; web-verified the competitive landscape. Findings are receipts-backed; fixes are tagged by owning lane for the team to action.*
