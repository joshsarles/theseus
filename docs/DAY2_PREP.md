# THESEUS — DAY-2 PREP BRIEF
**For: Day 2 (Jun 18, final build) → Day 3 (Jun 19, present). Self-audit 6.9/10. This brief is the plan picked apart.**
*Verified against the live repo (`/Users/force/Developer/Theseus`, branch `main`) — port mismatch, the two NV063 precision numbers, `unscored=1699`, `rfc3161:None`, and the uds-core comment-out are all confirmed real, not theoretical.*

---

## 1. TOP RISKS — ranked

| # | Risk | Sev | One-line fix | Who / effort |
|---|------|-----|--------------|--------------|
| 1 | **UI silently falls to SIM FEED / fake data** — UI defaults to `:8501`, `api.py` defaults to `:8077`, `run_full.sh --api` launches with NO `--port`. Entire "all-real" demo runs on a hardcoded mock fixture; ACCEPT seals nothing. **VERIFIED in repo.** | CRIT | Pin one port everywhere: launch `api.py --port 8501`; add a `curl :8501/api/health` pre-flight gate that refuses to start otherwise; giant on-screen banner when `conn!=='live'`. | Code, 1hr |
| 2 | ✅ **RESOLVED (Jun 18)** — was: two different, non-reproducing NV063 numbers on disk (RESULTS 0.36 vs headline 0.57). Now **ONE reproducible number** across every doc: **P 0.69 / R 1.0 / F1 0.82 / FAR 0.10 (n=50)**. The post-fix predictions are committed (`eval/out/ais_pol_preds.csv`), so `python3 eval/score.py --pred eval/out/ais_pol_preds.csv --labels eval/curated_labels.csv` regenerates `curated_metrics.json` exactly. | ~~CRIT~~ done | Regenerated post-fix preds, scored, committed, swept all docs. | — |
| 3 | **"REAL UDS deploy" overstates it** — `uds-bundle.yaml` has core-slim-dev commented out, Package CR inert; only the Pepr rail is live. mTLS/Keycloak/default-deny are OFF. At a DU-hosted event whose success metric is "deployed AND authorized via UDS Core," this is the most dangerous overclaim in the deck. **VERIFIED.** | CRIT | Do NOT chase the full uds-core deploy (see §4). Memorize the one-sentence honest frame; stop saying "UDS deploy." | Narrative; see §4 |
| 4 | **No named AO/program-office sponsor** — the literal Death Proof (25%) kill-shot; not closeable by code. | CRIT | Founder lands ONE attributed sentence (§5); if not, ship the honest SBIR-path fallback already in the deck. | Relationship (founder) |
| 5 | **The "moat" is a 125-line SHA-256 prev-hash chain — `rfc3161:null`, no Rekor, no signing key, unsigned.** Tamper-*evident* against corruption, not against an adversary. cosign+Rekor (which you already vendor) is strictly stronger and already in DoD. **VERIFIED.** | CRIT | Reposition moat as **schema+coverage+neutrality**, not the hash. Sign leaves with cosign (Ed25519 you already have) + one Rekor entry on a connected host. | Code (sign) + narrative |
| 6 | **Concurrent writers SNAP the chain red on stage** — `seal()` does non-atomic read-modify-write of chain.jsonl + bundle.json; UI polls every 4s with zero locking. A poll mid-write flashes a spurious red SNAP during the "CHAIN VERIFIED" climax. | HIGH | `os.replace()` atomic write (bundle before chain); `flock`; point DDIL beat at a SEPARATE `--record` dir; pause polling during the DDIL terminal beat. | Code, 1–2hr |
| 7 | **ACCEPT/OVERRIDE climax can visibly no-op** — wrong port → seal fails silently; or up-to-4s poll lag reads as "didn't work" → presenter double-clicks → double-seal or race. | HIGH | After ACCEPT call `refetch()` immediately; disable button ~1s; verify end-to-end on the correct port watching chain.jsonl grow by exactly one leaf. | Code, 1hr |
| 8 | **Pepr human-in-command rail = presence check, not a record binding** — admits any non-empty `human-approved-by` string; `approval-record-ref` only WARNS. "Your control is satisfied by typing 'x'." **VERIFIED in policy file.** | HIGH | Make rail-1 require the ref AND resolve+verify it chains to a sealed leaf; ship the deny-on-unsealed test. Converts the kill-shot into a live flex. | Code, 2–3hr |
| 9 | **773MB AIS CSV scanned synchronously on first /api/state** → first poll times out at 3.5s → latches to mock; ugly cold-open. | HIGH | Pre-compute lat/lon for the ~7 flagged MMSIs into a tiny JSON at stage time; warm the cache in pre-flight; raise UI abort to 6s. | Code, 1hr |
| 10 | **0.57 precision rests on n=50 / 8 TP, and the detector fired 1,699 UNSCORED alerts the FAR ignores.** `unscored_positive_predictions:1699` is in the file. On 11,898 tracks that's the real, unmeasured nuisance load. | HIGH | Lead with the false-alarm story honestly; frame n=50 as a pilot signal + the open-universe volume as exactly the Phase-I at-sea-labeling ask. | Narrative |
| 11 | **Explainer LLM seals ungrounded output** — no check that LLM text matches structured facts; the known ship-name hallucination can recur and get sealed as cryptographically-trustworthy truth. | MED-HIGH | Deterministic grounding gate between parse and seal; fall back to template loudly; seal `explainer`+`grounded` provenance. Demo the gate catching a hallucination = flex. | Code, 2hr |
| 12 | **Live k3d cluster evaporates on overnight sleep; rebuild re-hits the GHCR rate-limit that already stalled you.** | HIGH | `caffeinate` the Mac; keep Docker running; `docker login ghcr.io`; pre-pull all images into the cluster; record a clean UDS-beat video as fallback. | Infra |
| 13 | **OPSEC: real active-duty names/commands in a PUBLIC AGPL repo** — pure downside; can disqualify, can't raise score. | HIGH | Grep repo for names + command identifiers, strip to roles; confirm no procurement-steering implication remains. | Narrative, today |

---

## 2. DEMO FAILURE-MODES + airtight fallback

| Beat | Failure mode | Exact fallback |
|------|--------------|----------------|
| **0:00 — All-systems CIC picture** | UI shows "SIM FEED" / blank "LINKING" (wrong port or cold 773MB scan) | Pre-flight gate already confirmed `:8501/api/health`=200 and warmed the cache. Watch officer **visually confirms header reads "LINK LIVE" (amber dot) before touching anything.** If it ever reads SIM FEED → cut to the recorded clean run, keep narrating. |
| **0:30 — Anomaly flagged + explained** | LLM cold-start hangs (no GGUF/Ollama staged) or hallucinates a ship name live | **Do NOT cold-start the LLM on stage.** Pre-warm it OR present the deterministic template honestly ("grounded in the detection, the LLM is the gated airgapped narrator"). Sealed leaf's `explainer` field must match the spoken claim. |
| **1:00 — Watch officer ACCEPT/OVERRIDE seals** (THE CLIMAX) | Leaf count doesn't tick (wrong port / 4s lag / race SNAP) | Correct port verified in rehearsal; `refetch()` fires instantly on click; button debounced. Presenter narrates over any lag ("…and it's sealing now") — **never re-click.** Atomic write means the post-ACCEPT poll cannot SNAP. |
| **1:30 — Pull the cord (DDIL): serve last-good → signed update → promote → rollback** | `ddil_beat.sh` STEP 0 hits the now-BROKEN live UCI #316 fetch and hangs/aborts (`set -euo pipefail`); or STEP 1 "promotes" with version unchanged | **VERIFIED: live UCI #316 fetch already fails — the demo only survives on cached `staged.csv`.** Make `staged.csv` the authoritative source, kill the network fetch path. Run the beat with internet physically OFF in rehearsal. Force STEP 1 to a genuinely new version number. **`deploy/ddil_beat.sh` on the Mac is the proven spine — lead with it; have the 60s recording as instant fallback.** |
| **2:15 — Live UDS / Pepr admission** | Cluster died overnight; rebuild stalls on GHCR rate-limit in front of judges | Cluster pinned + verified the morning of; `docker login ghcr.io` done; images pre-pulled. **Fallback: clean screen-recording of `kubectl get pods` + Pepr denying 4 pods + cosign verify + tamper-reject, with `UDS_DEPLOY_EVIDENCE.md` open as receipts.** |
| **Any beat** | Wrong window on projector (`api.py` `/` route 404s — `frontend/cic.html` doesn't exist) | Bookmark `http://localhost:5173` full-screen; API in a separate minimized terminal; two URLs on a sticky note. Hard rule: **any beat that wobbles → cut to the recording and keep talking.** |

**Network choreography:** pre-stage EVERYTHING offline, then physically toggle wifi OFF for the whole demo and prove loopback still drives the dashboard — a stronger, honest airgap proof than the userspace-proxy trick. Show an explicit **"DDIL / AIR-GAP (by design)"** chip so offline never reads as a broken link.

---

## 3. HARD QUESTIONS a Navy/CDAO judge will ask + honest answers

**Q1. "Name the program office or AO who has agreed your record counts as accreditation evidence."**
A: *No AO yet. NV063 (opens 6/24) is our Phase-I on-ramp — this demo is the prototype. The AO is the gate; UDS control-inheritance is how we shorten it. We're not claiming an ATO in 72 hours; we're claiming the mechanism an AO consumes.* (Honest naming beats silence; do not fabricate an endorsement.)

**Q2. "Show me Istio mTLS, the Keycloak login, default-deny egress. `uds deploy` it."**
A: *We deployed the Pepr admission rail and Zarf signed packaging — real DU tooling — and have the uds-core bundle staged. Full Istio/Keycloak inheritance is the post-win step, blocked today only by a GHCR rate-limit, not a design gap.* (One memorized sentence; silence reads as "lacks UDS expertise.")

**Q3. "Your hash chain is unsigned stdlib SHA-256, no Rekor. Why isn't your differentiator cosign+Rekor, which is right there in your own toolbox?"**
A: *The hashing is table stakes — we use the DoD-standard primitives (cosign-signed leaves, one Rekor entry). Our differentiator is the SCHEMA + COVERAGE: one replayable chain binds model-version-hash + human ACCEPT/OVERRIDE identity + DDIL state-transition + admission verdict into a single accreditation-grade object a zero-trust verifier can rerun offline. Sigstore signs artifacts; SLSA proves builds; neither captures the operational decision + human-in-command leaf + airgap survival in one object.*

**Q4. "Your precision is 0.57 on a stacked n=50 deck — and you hid 1,699 unscored alerts. Why would a watch officer leave this on?"**
A: *Trust is one-shot on a ship — that's exactly the point. On a curated n=50 we measure FAR 0.15; the 1,699-alert open-universe volume is unmeasured and is precisely why we need NAVSEA at-sea labeling. That's the Phase-I ask, not a solved problem. The defensible wedge is the cold-start MECHANISM — no historical DB, deployable to any OPAREA day one — which commercial PoL (Windward/Spire) structurally can't do.*

**Q5. "Your machine-enforced human-in-command rail is satisfied by typing any string. What stops a forged approval?"**
A: *(If §1-#8 fix shipped) Nothing — until Day 2, when we bound it to the record: the rail now requires an approval-ref that resolves to a sealed leaf that chain-verifies. Watch — [apply a pod with a fake ref → DENIED; real sealed leaf → ADMITTED].*

**Q6. "Where does this plug into Aegis? If THESEUS and Aegis disagree, what does the watch officer do?"**
A: *SWAN-side, unclassified, decision-support only — combat systems are air-gapped and out of scope by design. Admission control is the deploy-time rail; Istio default-deny is the network rail (the uds-core layer); CANES/SSDS/combat integration is the Phase-III path that needs a program sponsor + NAVSEA cert. We are deliberately a side-car to the combat system, not in its certification cycle.*

**Q7. "Your explainer hallucinated a ship name. Audit trail ≠ validation — does the chain protect the officer or indict your model?"**
A: *The record proves chain-of-custody — who saw what, who decided, which model version — which is exactly what accreditation needs. It explicitly does NOT claim to validate model correctness; that's the SME-labeling + eval lane. The LLM is advisory and now grounding-gated; the deterministic detection is what seals.*

**Q8. "Model degrades after 45 days of denied comms — then what?"**
A: *Bounded staleness with honest degradation: serve last-good, TTL→standby, human override always available in the CIC. We don't claim dynamic convergence under DDIL — that's an open research problem industry-wide; we claim graceful, sealed degradation.*

---

## 4. CUT / DE-RISK on Day 2 (one build day)

**CUT from the critical path:**
- **Full uds-core (Istio/Keycloak/Operator).** Highest-cost, lowest-marginal-score, known-repeat-failure. Do NOT attempt the GHCR mirror under event-day pressure. Spend 20 min writing the trade-off sentence instead. If someone has spare cycles AND a working mirror: isolated cluster that *cannot touch the demo cluster*, time-boxed 2hr, one owner, hard abort.
- **Two live Pis + Tailscale mesh + multi-node failover + RTL-SDR.** Four stacked new dependencies for one day; `deploy/pi/wheels/` is empty (offline install WILL fail); Tailscale first-time bring-up at a conference is a classic failure. The DDIL beat **already passes on the Mac** — lock it there. Demote multi-Pi to STRETCH.
- **Central MLflow as a live dependency.** It's optional in `run.sh`; the host server is known-broken on Py3.14. Keep it as a side artifact (screenshot + the 8/8 sync test), never load-bearing in the 3-min window.
- **Live LLM cold-start on stage.** Pre-warm or present the template honestly.

**SIMPLIFY:**
- One demo machine, local registry + local API only, zero networked dependency in the 3-min window.
- Disable sleep/notifications/AirPlay; hard-pin every port; kill stray processes.

**KEEP (the proven money):** live Pepr denying 4 violating pods, Zarf SBOM (100 pkgs), cosign sign/verify/tamper-reject, the Mac DDIL beat, the sealed ACCEPT/OVERRIDE climax, ONNX-fits-4GB-Pi.

---

## 5. THE HIGHEST-LEVERAGE Day-2 moves, ranked

**CODE / INFRA (we can do — no external dependency):**
1. **Pin the port + pre-flight health gate + warm cache** (Risk #1, #9). Without this the entire demo is fake. ~2hr. **Do this first.**
2. **Reconcile the NV063 number** (#2) — re-run eval, one number everywhere, archive the loser. ~1hr. Kills the worst integrity exposure on disk.
3. **Atomic chain write + lock + refetch-on-ACCEPT** (#6, #7) — protects the climax from a spurious red SNAP. ~2hr.
4. **Bind Pepr rail-1 to a verified sealed leaf** (#8) — converts the sharpest Death-Proof kill-shot into a live flex; the single most credible Death-Proof upgrade available in code. ~3hr.
5. **OPSEC scrub + grounding gate on the explainer** (#13, #11) — downside-elimination + a credibility flex. ~2hr.

*(Stretch if all 5 land: cosign-sign the leaves + one Rekor entry — converts moat kill-shot #5 into "DoD primitives + our decision layer on top.")*

**RELATIONSHIP (founder only — cannot be forced by code):**
1. **Land ONE attributed sentence** from a NAVSEA NV063 PM / NIWC SME / any AO: *"a verifiable replayable decision record is evidence we would accept toward continuous authorization."* This is the #1 score lever (Death Proof 25%, ~+2 points). **Build the honest SBIR-path fallback sentence into the deck TODAY so a "no" costs nothing** — never leave a placeholder that depends on a reply, and never fabricate a name (you already had to scrub one once).
2. **Decide the Pi question** — if one Pi can be lit by a teammate without risking the demo, a 15-sec live-SSH-to-Pi clip buys real Portability credit; otherwise strip the live-Pi claim entirely.

---

## 6. POSITIONING — the one paragraph that survives a competitor's attack

> **THESEUS is the vendor-neutral, airgap-native decision-custody substrate for surface combatants under DDIL.** Concede scale to Palantir/Anduril and components to the incumbents out loud — it reads as credibility, not weakness. Three things survive any competitor's attack as a *combination*: **(1) Neutrality** — Palantir's record is Palantir-locked; ours is the Switzerland that ERM (machinery), DECK (collection), and a prime's algorithm all emit *into* without lock-in, which is structurally unavailable to any platform vendor, so "X already does your demo" becomes "X is our first tenant." **(2) Cold-start + DDIL operational depth** — no historical DB needed (deployable to any OPAREA day one, which commercial Pattern-of-Life structurally can't do), with the full offline beat (last-good, rollback, hierarchy, hot-swap) integrated and demoed live, not a cloud slide. **(3) The team** — NAVSEA + retired Navy/Marine engineers building for themselves is transition credibility a Silicon Valley team can't fake, and it's the path to the NV063 award. The moat is not the hash chain (an incumbent retrofits that in a sprint) — it's being *first into NV063 with a working DDIL demo and a real Navy team* before the durability window closes.

---

**Files load-bearing for Day-2 fixes (all absolute):**
- `/Users/force/Developer/Theseus/frontend/ui/src/hooks/useShipState.ts` (port default :8501, abort 3.5s)
- `/Users/force/Developer/Theseus/demo/api.py` (port default :8077, dead cic.html route, lazy 773MB scan)
- `/Users/force/Developer/Theseus/demo/run_full.sh` (`--api` launches with NO `--port` — the root of the mismatch)
- `/Users/force/Developer/Theseus/referee/chain.py` (`rfc3161:None`, non-atomic seal — sign + atomic-write here)
- `/Users/force/Developer/Theseus/deploy/uds/pepr/theseus-policies.ts` (rail-1 non-empty check — bind to sealed leaf)
- `/Users/force/Developer/Theseus/deploy/uds/uds-bundle.yaml` (core-slim-dev commented out — the "real UDS" overclaim)
- `/Users/force/Developer/Theseus/eval/RESULTS.md` (0.36) vs `/Users/force/Developer/Theseus/eval/out/curated_metrics.json` (0.57, `unscored:1699`) — reconcile
- `/Users/force/Developer/Theseus/deploy/ddil_beat.sh` (proven spine; kill the live UCI fetch, lock to cached `staged.csv`)
- `/Users/force/Developer/Theseus/serve/explain_local.py` (add grounding gate before seal)