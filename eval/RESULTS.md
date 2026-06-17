# NV063 anomaly eval — results (HONEST)

*Run Jun 17 2026 on real MarineCadastre US AIS (2024-01-01, first 1.5M rows, national).
Reproduce: `python3 demo/ais_pol.py --predictions eval/out/ais_pol_preds.csv && python3 eval/make_weak_labels.py --out eval/out/weak_labels.csv && python3 eval/score.py --pred eval/out/ais_pol_preds.csv --labels eval/out/weak_labels.csv`.*

## TL;DR
- **The eval harness works** (selftest passes; the plumbing — predictions → labels → P/R/FAR — is correct).
- **There is no anomaly ground truth yet**, so the precision/recall below are a **circular sanity check** (ais_pol vs same-family rules), **NOT a detection-skill claim**. Real NV063 P/R needs **OMTAD** (pending; harness is ready).
- **The honest, ground-truth-free, decision-relevant number is the alert VOLUME**: ais_pol fires **1,029 alerts across 11,898 tracks (8.6%)** over a 14.4 h national window = **71.6 alerts/hour**. That is too high for a single watch as-is → **tuning recommendations below** (loiter + dark-gap are 85% of the volume).

## 1. Harness validation `[verified]`
`python3 eval/score.py --selftest` → passes (TP/FP/FN/TN, precision, recall, false-alarm rate, F1 all correct). The scorer joins `(track_id, is_anomaly)` predictions against a labeled universe; unlisted/0 predictions count as not-flagged; `false_alarm_rate = FP/(FP+TN)`.

## 2. Circular sanity check — ais_pol vs weak rules `[pipeline-only]`
Scoring ais_pol's predictions against `make_weak_labels.py` (transparent PoL rules, **same family** as ais_pol):

| metric | value |
|---|---|
| n_labeled tracks | 11,898 |
| precision | **0.962** |
| recall | **0.882** |
| false-alarm rate | **0.0036** |
| F1 | **0.921** |
| TP / FP / FN / TN | 990 / 39 / 132 / 10,737 |

> ⚠ **NOT a performance metric.** Both sides are rule-based, so this measures *agreement between two rule implementations* (~92%), not detection skill against truth. The 39 FP / 132 FN come from a deliberate threshold difference (ais_pol's in-situ-envelope overspeed vs the labels' fixed 60 kn) — i.e., it quantifies **threshold sensitivity**, not error. It exists only to prove the eval path runs end-to-end on real data. **Do not quote as an NV063 result.**

## 3. Alert volume / false-alarm proxy `[verified]` — the honest number
No ground truth needed; this is just counting what the watchstander would see:

| | |
|---|---|
| tracks (≥4 fixes) | 11,898 |
| ais_pol alerts (deduped/track) | **1,029 (8.6% of tracks)** · raw 1,072 |
| by kind | loiter 574 · dark_gap 303 · overspeed 129 · position_jump 23 |
| data window | 14.4 h → **71.6 alerts/hour**, 86.5 per 1,000 tracks |

**Reading:** NV063's bar is a *watch-tolerable* rate (≈ **< 1 nuisance/watch**). 71.6/hour is a **national** feed (all US waters); the real deployment is **per-OPAREA** — bound `ais_pol --box <lat,lat,lon,lon>` to the area around a ship and the rate collapses. But even per-OPAREA, **loiter (56%) + dark_gap (29%) = 85% of volume** are the levers; they over-fire on benign behavior (anchorages; coastal AIS-coverage dropouts).

## 4. Tuning recommendations for `ais_pol.py` (WARHACKER applies — I don't edit it)
Grounded in the current thresholds (`demo/ais_pol.py::detect`):
1. **loiter (biggest driver, 574).** Current: `0.4 < still_frac < 0.95` and `max(sog) > 3 kn`. This flags normal anchored/fishing dwell. → Raise the still-fraction floor (`0.4 → ~0.6`), add an **absolute** still-duration gate (e.g. ≥ 30 min, not just a fraction), and **exclude `Status == 1` (at anchor)** explicitly. Expect a large volume drop with little real-signal loss.
2. **dark_gap (303).** Current: any gap `> 30 min` while `sog > 1 kn`. Coastal terrestrial-AIS coverage routinely drops > 30 min — that's a coverage artifact, not AIS-off. → Raise to **45–60 min**, lower confidence for shorter gaps, and (when available) suppress in known low-coverage ranges / corroborate with a second sensor before alerting.
3. **overspeed (129).** Current: `> 1.5× in-situ envelope`, single-fix. Bad GPS fixes spike this. → Require **N consecutive** over-envelope fixes (not one), and gate on fix quality.
4. **position_jump (23).** Precise and low-volume — **keep as is** (highest-value, lowest-noise alert).
5. **Cross-cutting:** make `--box` (per-OPAREA scoping) the default operating mode for the watch-tolerance number; add an alert **confidence floor** for emission; consider an explicit **"alerts per watch" budget** that the cell tunes to.

## 5. Honest gap + next step
- **No ground truth.** §2 is circular; §3 is volume, not accuracy. The only path to a real NV063 precision/recall/false-alarm number is **labeled data**: pursue **OMTAD** acquisition (license UNVERIFIED — `docs/research/datasets/DATASETS.md` §6). The harness is **label-source-agnostic** and ready the moment labels land.
- **GFW** dark-vessel/loitering labels are richer but **NON-COMMERCIAL** → internal validation only, never a deliverable number.
- After tuning (§4), re-run §3 per-OPAREA to show a watch-tolerable rate — that is the demo-credible number we *can* state honestly today.
