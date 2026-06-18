# NV063 anomaly eval — results (HONEST)

*Updated Jun 17 2026 on real MarineCadastre US AIS (2024-01-01, first 1.5M rows, national).*

## TL;DR
- **Current NV063 signal (post-fix), n=50 analyst-curated set: precision 0.69 · recall 1.0 · F1 0.82 · false-alarm 0.10** (FP 16→4). This **supersedes** the pre-fix 0.36 / 1.0 / 0.53 / 0.39 baseline forensically documented in §2 — the lift came from landing the two fixes below, *not* from re-labeling. **One number, one place — and reproducible:** `python3 eval/score.py --pred eval/out/ais_pol_preds.csv --labels eval/curated_labels.csv` regenerates `eval/out/curated_metrics.json` (= this headline = `ROADMAP.md`). The predictions file is committed, so a fresh clone re-scores the headline without the raw 807 MB AIS source.
- **The two dominant false-positive causes are now FIXED:** (1) the AIS **SOG = 1023 "not available" sentinel** misread as a 102 kn overspeed → dropped; (2) **position_jump over-fired on high-cadence feeds** (GPS jitter) → **cadence-aware ≥ 0.5 nm distance gate** (validated cross-region on Ushant: 3151→771 false jumps). *(loiter over-fire on dwelling ferries/tugs was separately tuned.)*
- **Honest framing:** n=50, analyst-curated, **pending NAVSEA SME validation**; anomaly-enriched (sample FAR ≠ population FAR). The detector also fires **~1,699 alerts on the open universe (~11.9k tracks) that this n=50 set does not score** — that unmeasured nuisance load is exactly the Phase-I at-sea-labeling ask, not a solved problem.

## 1. Harness validation `[verified]`
`python3 eval/score.py --selftest` passes. Scorer joins `(track_id, is_anomaly)` predictions vs a labeled universe; `false_alarm_rate = FP/(FP+TN)`.

## 2. Analyst-curated eval — the real (non-circular) number `[verified, SME-pending]`
**Method (breaks the circularity):** `eval/curate_oparea.py` drew a **stratified** sample — 25 of ais_pol's flags + 25 random un-flagged tracks (eligible pool 11,773, ≥6 fixes). Each was adjudicated to `is_anomaly` in `eval/curated_labels.csv` **from the track's own evidence** (declared AIS NavigationStatus + vessel type + full kinematic profile) — a basis **independent of ais_pol's fixed thresholds**. Scored ais_pol's predictions against it:

| metric | value | note |
|---|---|---|
| n_labeled | 50 | 25 flagged + 25 clean (stratified) |
| TP / FP / FN / TN | 9 / 16 / 0 / 25 | |
| **precision** | **0.36** | of 25 random flags, 9 true → unbiased est. of ais_pol precision (95% CI ≈ 0.18–0.57, n=25) |
| **recall** | **1.0** | 0 missed in 25 unflagged — small-n, wide CI (not "perfect") |
| false-alarm rate (sample) | 0.39 | **enriched** sample; **population FAR ≈ 5–6%** (≈64% of ~1029 flags are FP / ~10.9k true-neg) |
| F1 (sample) | 0.53 | enriched; not a population F1 |

**The 16 false positives break down as:**
- **SOG=102.3 "not available" sentinel misread as overspeed** (e.g. 368119660 moored, 367402250 ferry) — a genuine ais_pol bug, see §5.1.
- **Ferries** dwelling at terminals flagged loiter (367362520, 368249350, 367090270, 367324580 — passenger type 60).
- **Working tugs / fishing vessels** flagged loiter (367164240, 368005880, 367080670, 367430810).

**The 9 true positives:** stationary tugs/towing declared "underway" for 5+ h (366946850, 367352250, …), a transited-then-loitered HSC (338519000), and genuine multi-hour **AIS dark gaps** on transiting cargo/pleasure (563033500 75 min, 636016824 6.3 h, 367731170 6.2 h).

> **Caveats (loud):** n=50, analyst-curated **pending NAVSEA SME validation**; the precision estimate is sensitive to the "is a stationary tug anomalous?" calls (SME-dependent). Stratified/anomaly-enriched, so the sample FAR ≠ population FAR. This is a pilot signal, not a production metric.
>
> **⚑ The §2 table above is the PRE-FIX forensic baseline** (kept to show the bugs we found + fixed). **Current headline (post SOG + cadence fixes), same n=50 set:** precision **0.69** · recall **1.0** · F1 **0.82** · FAR **0.10** (FP 16→4, all 9 TPs caught) — reproducible via `eval/score.py` against the committed `eval/out/ais_pol_preds.csv` → `eval/out/curated_metrics.json`; cross-region check in `docs/research/CROSS_REGION_VALIDATION.md`.

## 3. Circular weak-label sanity check `[pipeline-only]` (kept for completeness)
ais_pol vs `make_weak_labels.py` (same rule family): P 0.962 / R 0.882 / FAR 0.0036 / F1 0.921 over 11,898 tracks. **Not a performance metric** — measures rule-implementation agreement (~92%), validated only that the eval path runs. Superseded by §2 as the real signal.

## 4. Alert volume / false-alarm proxy `[verified]`
ais_pol fires **1,029 alerts over 11,898 tracks (8.6%)** in a 14.4 h national window = **71.6/hour** (loiter 574 · dark_gap 303 · overspeed 129 · jump 23). NV063's bar is watch-tolerable (≈ <1 nuisance/watch) → bound to `--box` per-OPAREA; §2 shows ~64% of flags are FP, so tuning (§5) is the lever.

## 5. Tuning recommendations for `ais_pol.py` (WARHACKER applies — I don't edit it)
**5.1 NEW — fix the SOG=102.3 sentinel bug (highest priority, it's a bug not a threshold).** AIS encodes "speed not available" as 1023 → SOG = **102.3 kn**. ais_pol's overspeed (`max(sogs) > 1.5×envelope`) treats 102.3 as a real 102 kn → false overspeed on any track with a missing-SOG record. **Filter `SOG >= 102.2` (and 102.3) out of all speed logic** before detection. (Several §2 false positives were purely this.)
**5.2 loiter (biggest volume driver).** Raise still-fraction floor 0.4→~0.6, add an absolute still-duration gate (≥30 min), exclude `Status==1` (anchor) **and** down-weight known dwellers (passenger/ferry type 60; working tugs type 52; fishing type 30) — §2 shows these dominate the loiter FPs.
**5.3 dark_gap.** 30→45–60 min; lower confidence for short gaps; suppress in known low-coverage ranges. (The real TPs in §2 had gaps of 75 min–6.3 h.)
**5.4 overspeed.** Require N consecutive over-envelope fixes (after the 5.1 sentinel fix).
**5.5 position_jump.** Keep — precise, low-volume, was a clean TP source.

## 6. Ground-truth status + next step
- **OMTAD is unusable.** It contains **only normal trajectories, no anomaly labels** (confirmed verbatim by its NeurIPS'25 extension), and has no license file. The arXiv extension's labels are synthetic + unreleased + CC BY-NC-ND. **Do not ship on OMTAD.**
- **Global Fishing Watch** has *real* dark-vessel/loitering/rendezvous labels but is **CC BY-NC** (non-commercial). **Action:** pursue a GFW commercial-use grant (`info@globalfishingwatch.org`) to unlock them for benchmarking.
- **Primary path:** grow the §2 analyst-curated set (more tracks, more OPAREAs, NAVSEA SME sign-off) → a defensible, license-clean NV063 precision/recall. The harness + curation tooling are built and ready.
