# Cross-Region Validation — THESEUS Cold-Start AIS Pattern-of-Life Detector

**Claim under test (NV063):** the AIS Pattern-of-Life detector in `demo/ais_pol.py`
is *cold-start* — it carries no historical database and no region-specific tuning.
It builds its "normal" speed envelope **in situ** from whatever op-area it is pointed
at, then flags loiter / dark-gap / overspeed / position-jump against that in-situ
baseline. **If it runs on a completely different region with zero retraining and zero
code changes, the cold-start design generalizes** (it is not overfit to the US
MarineCadastre data it was built against).

This document records a **real** test of that claim on a second region — the **Ushant
Traffic Separation Scheme off Brittany, France** — using a different data source with a
different schema. Everything below ran on real data. No mocks.

---

## TL;DR Verdict

**The cold-start *envelope mechanism* generalizes cleanly. The fixed-threshold *rules*
are sampling-cadence-sensitive and over-fire on Ushant's dense sampling — an honest,
explainable limitation, not a failure of the cold-start design.**

- The unchanged detector ran end-to-end on 7.13 M Ushant fixes (18,603 tracks) and
  **sealed a tamper-evident record that verifies PASS** — same binary, `--csv` only.
- The in-situ envelope **auto-fit Ushant's traffic**: it learned a 24 kn speed cap
  purely from Ushant's own vessels, with no US priors leaking in. This is the core
  cold-start property and it worked exactly as designed.
- Alert *profile* differs sharply between regions, and **we can explain every bit of
  the difference from data properties** (vessel mix, field availability, sampling
  cadence) rather than from detector overfitting. See "Why the profiles differ."

---

## Data

| | US baseline | Ushant (cross-region) |
|---|---|---|
| Source | MarineCadastre US AIS (public domain) | Zenodo "Ushant AIS" — Gloaguen et al. 2019 (ANR/Astrid SESAME, data via CLS) |
| Region | US coastal waters | Ushant TSS, West of Brittany, France — one of the world's densest shipping lanes |
| File | `data/datasets/marinecadastre_us/AIS_2024_01_01.csv` | `data/datasets/ushant/data/traj_*.txt` (18,603 files) |
| Native schema | `MMSI,BaseDateTime,LAT,LON,SOG,COG,…,VesselType,Status,…` (17 cols) | `"x";"y";"vx";"vy";"t"` (5 cols, `;`-delimited, one file per track) |
| Coords | decimal degrees | decimal degrees (`x`=lon, `y`=lat) — **no conversion** |
| Speed | `SOG` in knots | `SOG := sqrt(vx² + vy²)`, `vx/vy` already in knots per README — **no conversion** |
| Time | absolute ISO-8601 | `t` = seconds **since track start** (relative); synthesized to ISO-8601 |
| Identity | real `MMSI` | anonymized — synthetic 9-digit `990xxxxxx` from file index (1 file = 1 track) |
| `VesselType` | present | **absent** (omitted → detector uses `other` fallback bucket) |
| `Status` | present | **absent** (omitted → loiter rule, which keys on `Status==0`, is suppressed) |

The Ushant schema and units are confirmed directly from the dataset `READ_ME.html`:
*"vx is the x-velocity (in knots) given in the AIS message … t the time since the
beginning of the trajectory (in seconds)."*

### Adapter

`ingest/ushant.py` maps the Ushant schema → the exact columns `ais_pol.py` expects
(`MMSI, LAT, LON, SOG, BaseDateTime`) and writes
`data/datasets/ushant/ushant_normalized.csv` (427 MB, gitignored).

- **Honest unit mapping** (no silent conversions): SOG and coords are already in the
  detector's units; only the timestamp is synthesized. Because `ais_pol` only ever
  uses **time deltas within a single MMSI track** (gaps, implied speed), the absolute
  anchor is immaterial to detection — we anchor at a fixed neutral epoch and stagger
  tracks for reproducibility.
- **Idempotent**: re-running the adapter produces byte-identical output (verified).
- Output: **18,603 tracks / 7,131,993 rows / max SOG 30.0 kn** — matches the dataset's
  stated "18,603 trajectories, >7 M GPS observations."

---

## Method (exactly what ran)

```bash
# 1. Normalize Ushant → MarineCadastre-style CSV (no detector changes)
python3 ingest/ushant.py
#   → data/datasets/ushant/ushant_normalized.csv  (18,603 tracks · 7,131,993 rows)

# 2. Run the UNCHANGED detector on Ushant
python3 demo/ais_pol.py \
  --csv data/datasets/ushant/ushant_normalized.csv \
  --rows 8000000 \
  --predictions out/ushant_predictions.csv

# 3. Run the UNCHANGED detector on the US set (side-by-side)
python3 demo/ais_pol.py \
  --csv data/datasets/marinecadastre_us/AIS_2024_01_01.csv \
  --rows 8000000 \
  --predictions out/us_predictions.csv
```

`demo/ais_pol.py` was **read but not modified**. The only difference between the two
runs is the `--csv` path.

---

## Results — side by side (REAL numbers)

| | US (MarineCadastre) | Ushant (Brittany) |
|---|---:|---:|
| Rows scanned | 7,296,275 | 7,131,993 |
| Tracks built | 14,868 | 18,603 |
| **In-situ envelope (learned, kn)** | cargo≤19, fishing≤17, other≤22, passenger≤28, tanker≤18 | **other≤24** |
| Total alerts | 1,768 | 10,836 |
| Tracks flagged | 1,727 (**11.6%**) | 10,836 (**58.2%**) |

**Per-type alert counts:**

| Alert type | US | Ushant |
|---|---:|---:|
| loiter | 568 | **0** |
| dark_gap | 1,013 | 7,685 |
| overspeed | 90 | **0** |
| position_jump | 97 | 3,151 |

**Normalized (alerts per 10,000 tracks):**

| | total | loiter | dark_gap | overspeed | position_jump |
|---|---:|---:|---:|---:|---:|
| US | 1,189 | 382 | 681 | 60 | 65 |
| Ushant | 5,825 | 0 | 4,131 | 0 | 1,694 |

**Record integrity:** both runs sealed into the tamper-evident chain and
**`verify_dir` → PASS** (156 leaves after both runs; merkle root reproducible). The
cold-start run on a brand-new region produced a verifiable, offline-auditable record
with no special handling.

---

## Why the profiles differ (the honest analysis)

The Ushant flag rate (58.2%) is ~5× the US rate (11.6%). This is **not** the detector
"breaking" or being miscalibrated for the region — every component of the gap traces
to a measurable property of the Ushant data, and the cold-start envelope did its job.

### 1. The in-situ envelope generalized correctly ✅
The detector learned `other≤24 kn` for Ushant purely from Ushant's own traffic — its
p99 SOG. Independent profiling of the raw files gives p99 ≈ 25 kn, so the learned cap
is right. No US speeds leaked in. **This is the cold-start claim, and it held.**
(Ushant collapses to a single `other` bucket only because the source has no
`VesselType` field — see point 4.)

### 2. `loiter = 0` and `overspeed = 0` are *structural*, not failures
- **loiter** requires `Status == 0` (underway) fixes near zero speed. Ushant has **no
  Status field**, so the rule's underway gate never fires — loiter is *suppressed by
  data availability*, exactly as the adapter documents. The detector did not
  false-suppress; the input simply lacks the field.
- **overspeed** requires 3 consecutive fixes above **1.5×** the in-situ cap (>36 kn).
  Ushant is clean, well-separated lane traffic capping ~27–30 kn — almost nothing
  sustains >36 kn. Zero overspeed is the *correct* answer for this region.

### 3. `position_jump` over-fires due to **sampling cadence**, not spoofing
This is the most important honest caveat. Characterizing the 63,935 segment-level
position-jump triggers in Ushant:
- **96%** occur over an inter-fix gap of **< 30 s** (median dt = **8 s**).
- **50%** span **< 0.5 nm**.

Ushant is sampled very densely (median inter-fix dt ≈ **8–14 s**) vs the US set
(median dt ≈ **71 s**, i.e. ~1–2 min). The detector's `position_jump` rule computes an
*implied speed* = distance / dt. Over an 8-second interval, even small GPS jitter
(0.1–0.3 nm) yields a huge implied speed (hundreds of kn), tripping the gate. So the
3,151 Ushant position-jumps are **dominated by dense-sampling GPS jitter**, not genuine
GNSS spoofing/identity-swap. On the coarser-cadence US data the same rule barely fires
(97 alerts). **The rule is cadence-sensitive; the cold-start envelope is not.**

### 4. `dark_gap` over-fires due to **the dataset's own collection gaps**
The Ushant README states time lags range "5 seconds to 15 hours, with 95% of lags
below 3 minutes" — i.e. long sampling gaps are an inherent property of this
satellite+coastal collection, especially offshore. The 7,685 dark-gap alerts have
median gap ≈ **77 min** (the rule fires >45 min while underway). Many are collection
gaps in the *source feed*, not vessels actively going dark. The rule behaves
identically to the US run; Ushant simply has more long gaps to catch.

---

## Are the Ushant anomalies plausible? (face validity)

Yes, where the rules are cadence-robust:
- **dark_gap** examples surface vessels that were underway at 10–17 kn and then
  disappeared from the feed for 1–6 h — exactly the cue ("cue another sensor; flag
  possible dark-vessel behavior") a watchstander wants in a TSS, even if many are
  benign coverage gaps. The detector's *explanation* is correct and actionable.
- **position_jump** examples are honestly mostly jitter artifacts at this sampling
  rate (see point 3) and should be read as a tuning signal, not as detections.

The detector produces the same plain-language, sealed, explainable alerts on Ushant as
on the US — a watchstander gets a reason + recommended action for every flag, in a
region the system had never seen.

---

## Verdict (honest)

**Does cold-start generalize? Yes — the mechanism that matters does.**

1. **Core cold-start claim — CONFIRMED.** The unchanged detector ran on a brand-new
   region, with a different source schema and a different traffic mix, and built a
   correct in-situ "normal" envelope (24 kn) from Ushant's own data with **zero
   retraining and zero code changes**, sealing a record that verifies PASS. It is not
   overfit to MarineCadastre/US data.

2. **Honest limitation — the fixed thresholds are cadence-sensitive.** The
   `position_jump` implied-speed gate and the `dark_gap` minute gate are tuned implicitly
   to US AIS cadence (~1–2 min inter-fix). On Ushant's much denser sampling (~8 s) the
   position-jump rule over-fires on GPS jitter, and the long-gap-prone Ushant feed
   produces many dark-gap alerts. This inflates the Ushant flag rate to 58.2% vs the
   US 11.6%. **This is a threshold/cadence issue, not a cold-start failure** — and the
   per-segment characterization (96% of jumps over <30 s gaps) makes the cause
   unambiguous.

3. **Recommended hardening (out of scope here — `ais_pol` is not ours to rewrite in
   this task):** make the jump/gap gates cadence-aware — e.g. require a minimum dt
   before computing implied speed, or scale the dark-gap threshold to each track's own
   median inter-fix interval. That would make the *rules* as cold-start-robust as the
   *envelope* already is, without any region-specific constants.

**Bottom line for NV063:** the strongest cold-start evidence holds — the in-situ
baseline adapts to a never-seen region on contact. The alert thresholds need
cadence-normalization to keep the false-positive profile stable across regions, and we
can show exactly why from the data.

---

## Reproduce

```bash
cd /Users/force/Developer/Theseus

# normalize Ushant (idempotent; ~30 s; writes 427 MB gitignored CSV)
python3 ingest/ushant.py

# Ushant (cross-region)
python3 demo/ais_pol.py --csv data/datasets/ushant/ushant_normalized.csv \
  --rows 8000000 --predictions out/ushant_predictions.csv

# US (baseline)
python3 demo/ais_pol.py --csv data/datasets/marinecadastre_us/AIS_2024_01_01.csv \
  --rows 8000000 --predictions out/us_predictions.csv

# verify the sealed record
python3 -c "import sys; sys.path.insert(0,'.'); from referee.chain import verify_dir; \
from pathlib import Path; print(verify_dir(Path('demo/out/record')))"
```

Artifacts: `ingest/ushant.py` (adapter), `out/ushant_predictions.csv`,
`out/us_predictions.csv`, `demo/out/record/` (sealed chain).

*All figures in this document are from the real runs above (THESEUS, Jun 17 2026).*
