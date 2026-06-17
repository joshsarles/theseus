# DON26BZ03-NV063 — Technical Approach (Phase I draft)

**Topic:** Anomalous Behavior Detection & Alerting for Congested Maritime Environments (NAVSEA, DON SBIR 26.3 / R3; opens 6/24, closes 7/22).
**Offeror system:** THESEUS — an airgapped, tamper-evident onboard maritime decision-support substrate. Advisory; the watch team commands. SWAN-side; alongside SSDS via certified data pipes, never embedded in the kill chain in Phase I.

> **Integrity discipline (founder rule):** every capability below is tagged **[BUILT]** (running code in this repo, with a file path + a real number), **[PARTIAL]** (substrate built, integration pending), or **[PROPOSED]** (Phase I/II work, not yet built). Nothing aspirational is stated as built. Banned framings avoided: no "autonomous"/"AI decides", no "replace SSDS", "tamper-evident not tamper-proof", "building to CMMC L2 (audit pending)".

---

## 1. The requirement (NV063, verbatim intent)
Automated **Pattern-of-Life** of surface + air contacts around Navy ships via **AIS + ADS-B + radar fusion**, with **explainable-AI** alerting, that works **without a large historical database** and **in novel OPAREAs**, integrating with the **Ship Self-Defense System (SSDS)** (live SSDS integration = Phase III). The hard differentiator is the **cold-start** constraint: learn "normal" on the fly where no prior data exists.

## 2. Approach — what we do, and what's already real

### 2.1 Cold-start, in-situ Pattern-of-Life **[BUILT]**
THESEUS learns the "normal" speed envelope **in-situ from the op-area's own traffic** — no historical DB. `demo/ais_pol.py::load_tracks` computes a per-vessel-class **99th-percentile SOG envelope** from the contacts currently in view; `detect()` then flags deviations. Verified on real MarineCadastre US AIS (1.5M rows): builds 11,898 tracks + a per-class envelope and screens them in **~4 s, single-core, pure stdlib** (edge-feasible). This directly answers "no large historical DB / novel OPAREA."

### 2.2 Explainable alerts, advisory only **[BUILT]**
Every alert carries a plain-language **why** + a **recommended action** for the watchstander (e.g. *"transited then loitered: 18/22 fixes <0.5 kn over 3.1 h → verify intent; flag for watch"*). Four detectors today: **loiter, AIS dark-gap, position-jump (spoof), overspeed**. The cell **drafts; the human decides** — it never acts. (`demo/ais_pol.py::detect`.) Real run: **1,029 alerts over 11,898 tracks**; honest tuning path to a watch-tolerable rate in `eval/RESULTS.md`.

### 2.3 AIS + ADS-B + radar fusion **[PARTIAL]**
- **AIS** ingest + PoL: **[BUILT]** (above).
- **ADS-B** (air picture): **[BUILT]** capture path — own-SDR (`dump1090-fa`) on a Pi, fully airgapped (`docs/research/SDR_CAPTURE_PLAN.md`); cross-correlation with AIS is **[PROPOSED]** (no open dataset co-registers AIS+ADS-B+radar — we build the fusion ground-truth via the Stone Soup simulator, `docs/research/datasets/DATASETS.md` §5).
- **Radar**: **[PROPOSED]** — synthetic multi-sensor detections + ground truth via Stone Soup (MIT) for cold-start fusion dev; live shipboard radar at the edge. AIS↔radar coregistration under sensor disagreement is the named research wedge.

### 2.4 The tamper-evident accreditation record — the moat **[BUILT]**
Every alert (and every model promotion) is sealed into a **hash-chained, Merkle-rooted, offline-verifiable** record (`referee/chain.py`); tampering one byte snaps the chain at that leaf. Verified this run: **162 leaves, verify PASS**. This is the trust/accreditation substrate the Navy's onboard-AI fielding blocker actually needs — explainable + replayable + un-quietly-editable. ("Tamper-evident, not tamper-proof"; the production signed ledger is the retained-IP upgrade of the same append/verify seam.)

### 2.5 Edge deploy under DDIL **[BUILT, deploy lane]**
Ships from one **UDS/Zarf** airgap bundle to a disconnected cluster; **NIST 800-53 evidence via Lula** travels with it (AU-9 audit-protection + CM-3 config-control are live OPA validations; `lula/component-definition.yaml`). Runs fully disconnected; rollback-to-last-good on a node with no shore link. (Deploy lane: `deploy/`, `zarf/`, `lula/` — verified per the event repo.)

### 2.6 Human-in-command + SWAN-side **[BUILT, by construction]**
Alerts are advisory; the human accepts/overrides and that decision is sealed. v1 is **SWAN-side only** (combat-system data is hard-air-gapped/classified — out of scope until a later classified variant). We **compose with** SSDS via certified data pipes; we do not embed in or replace it.

## 3. Metrics + evidence (real, with honest caveats)

| Capability | Evidence | Number | Status |
|---|---|---|---|
| Machinery health (naval GT, the SWAN-side organ) | `models/benchmark.py` / loop registry | **RMSE 0.00382** (3.8× vs mean baseline) on real frigate-GT decay | [BUILT] |
| GT-RUL transfer | `models/benchmark.py` (C-MAPSS, unit-split) | RMSE 50.88 cyc (floor; not the capped official protocol) | [BUILT, caveated] |
| Real-failure anomaly | `models/benchmark.py` (MetroPT-3) | F1 0.94 — **leakage-inflated**; needs leave-one-failure-out CV | [BUILT, caveated] |
| Cold-start AIS PoL | `demo/ais_pol.py` on MarineCadastre | 11,898 tracks + in-situ envelope screened in ~4 s | [BUILT] |
| AIS anomaly precision/recall | `eval/score.py` | **no ground truth yet** — circular sanity check only; OMTAD pending | [PARTIAL] |
| Tamper-evident record | `referee/chain.py` + this run | 162 leaves, verify PASS | [BUILT] |

**Honesty:** we cannot yet state an AIS-anomaly precision/recall against truth (no labeled OPAREA set; OMTAD acquisition is the path — `eval/RESULTS.md` §5). What we *can* state today is the cold-start mechanism, the explainable-alert volume + a tuning path to a watch-tolerable rate, the machinery-organ accuracy, and the verified record.

## 4. Phase I scope + integration path
- **Phase I:** the cold-start PoL + explainable-alert cell on AIS(+ADS-B), the tamper-evident record, the airgap deploy + compliance evidence; establish a labeled OPAREA eval (OMTAD or a customer-furnished set) and report real precision/recall/false-alarm rate at a watch-tolerable threshold.
- **Integration (do NOT embed in the kill chain in Phase I):** run **alongside SSDS reading certified data pipes** in a separate container (the Maven/Palantir pattern) — see `docs/research/datasets/DATASETS.md` SBIR notes. Live SSDS integration is **Phase III**.
- **Latency design target (Phase III):** ML inference < 5 s (radar scan ~10 s + fusion ~5 s), total alert < ~30 s, on edge GPU/FPGA within ship power/thermal — designed for from Phase I (the stdlib cell already screens 1.5M contacts in ~4 s).
- **Standards:** MOSA-aligned; UMAA Distro-A ICDs over OpenDDS; COLREGs reasoning off the public-domain US Navigation Rules.

## 5. Cold-start architecture roadmap (staged) **[PROPOSED]**
To beat commercial players that assume weeks-to-months of data accumulation:
1. **Physics-informed priors** (vessel kinematics) → useful at t=0 with ~10–20 tracks, no baseline. *(In-situ envelope is the [BUILT] first step.)*
2. **Few-shot / LLM transfer** from global AIS → week-1.
3. **Synthetic augmentation** (COLREG sims, GAN-AIS) → weeks 1–4.
Explainability via SHAP/symbolic-neural + atomic natural-language alerts (the [BUILT] why+action lines are the seed). Unsupervised **autoencoder** (reconstruction-error) for thin/unlabeled telemetry is the recommended deeper anomaly model (`docs/research/MODEL_BENCHMARKS.md`).

## 6. Honest status summary
**[BUILT] today:** cold-start in-situ PoL · explainable advisory alerts · the tamper-evident record (verified) · airgap deploy + Lula compliance · machinery organ (real numbers) · human-in-command.
**[PARTIAL]:** AIS+ADS-B+radar fusion (AIS built; ADS-B capture built; fusion GT + radar = build items) · AIS-anomaly precision/recall (harness ready; needs labeled data).
**[PROPOSED]:** PINN + few-shot/LLM + synthetic cold-start stack · autoencoder anomaly model · live SSDS integration (Phase III) · calibrated/conformal alerting.

*Every [BUILT] claim is reproducible from this repo; every number traces to a script + a path. Drafted by THESEUS lane; verify against the cited code before external use.*
