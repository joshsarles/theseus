# THESEUS — ingest adapters

One normalizer per dataset. Each reads a **local downloaded dataset** (`data/datasets/`, gitignored — see `docs/research/datasets/DOWNLOADS.md`) and emits the **loop's data contract**:

> a CSV with **numeric feature columns** and the **LAST column = the target**.

Outputs go to `ingest/out/<name>.csv` (gitignored — derived data). They drop straight into WARHACKER's loop via the wired entrypoint:

```bash
python3 ingest/cbm.py
python3 demo/stage_data.py --input ingest/out/cbm.csv   # copies + seals data_staged
python3 demo/retrain.py                                  # trains + registers theseus-cbm/v(N)
```

## The adapters (all run on REAL data, verified Jun 17–18)

| Adapter | Source (license) | Rows / shape | Target (last col) | Loop status |
|---|---|---|---|---|
| `cbm.py` | UCI #316 Naval Propulsion CBM (CC BY 4.0) | 11,934 × 18 | `gt_compressor_decay` | **LOOP-LIVE** — sklearn GBR RMSE **0.00382** (= demo's ~0.0038) |
| `cmapss.py` | NASA C-MAPSS FD001 (US-Gov public) | 20,631 × 25 | `rul` | staged-ready ‡ |
| `ncmapss.py` | NASA N-CMAPSS DS02 (US-Gov public) | 52,635 × 19 (dev, `--stride 100`) | `rul` | staged-ready ‡ |
| `metropt.py` | MetroPT-3 air compressor (CC BY 4.0) | 25,515 × 16 (600 s windows) | `is_anomaly` (498 pos) | staged-ready ‡ |
| `marinecadastre.py` | MarineCadastre US AIS (public domain) | 11,898 tracks (1.5 M rows scanned) × 11 | `weak_anomaly_heuristic` (1,122 pos) ⚠ | staged-ready ‡ |

‡ **`demo/retrain.py` currently hardcodes `TARGET = "gt_compressor_decay"`**, so only `cbm.csv` trains through the loop *today*. `cmapss/ncmapss/metropt/marinecadastre` already satisfy the uniform contract (last col = target) and become loop-live the moment `retrain.py`'s target is parametrized (e.g. `--target rul`). **Flagged to WARHACKER** (retrain.py is their lane).

## Per-adapter notes (HONESTY-FIRST)
- **`cbm.py`** — real frigate gas-turbine decay; emits the 16 UCI features + `gt_turbine_decay` (the secondary UCI target, which `retrain.py` drops as a non-feature) + `gt_compressor_decay` last. The 0.00382 RMSE proves the CSV is loop-equivalent to the demo's built-in `ucimlrepo` fetch, but works **offline from the local zip** (no network).
- **`cmapss.py`** — `rul = max_cycle(unit) − current_cycle` (standard C-MAPSS label). `--subset FD001..FD004`. Raw RUL (no piecewise cap; cap at 125 downstream if desired).
- **`ncmapss.py`** — NASA **N-CMAPSS** (Turbofan Degradation Sim Data Set 2), the realistic full-flight-condition successor to C-MAPSS. Reads `data/datasets/ncmapss/N-CMAPSS_DS02-006.h5`; emits the operating-condition channels `W` (4) + measured sensors `X_s` (14) as features with `rul` (the dataset's own `Y`) last. Column names are read from the file's `*_var` arrays. `--split dev|test` (train units 2,5,10,16,18,20 / test 11,14,15), `--units`, `--stride` (1 Hz source → default 100), `--rows`. **Validated on real DS02** (`N-CMAPSS_DS02-006.h5`, 2.45 GB, sha256 `47971a68…ca765`): `--stride 100` → 52,635 rows × 19, dev units 2,5,10,16,18,20, `rul` ∈ [0,88]; `--split test` selects units 11,14,15.
- **`metropt.py`** — aggregates the 1.5 M-row 1 Hz stream into 600 s windows of per-sensor means; `is_anomaly = 1` if the window overlaps one of the **four company-reported air-leak failure windows** from the dataset's Data Description (real failure reports, not invented). `--window` tunes the bucket size.
- **`marinecadastre.py`** — per-track kinematic features. **`weak_anomaly_heuristic` is WEAK SUPERVISION, not ground truth** — distilled from transparent Pattern-of-Life rules (loiter / dark-gap / overspeed / position-jump), the same family as `demo/ais_pol.py`. Use only to train a fast model that *mimics* the rule detector. For honest anomaly metrics use the **`eval/` harness** with real labels (OMTAD). `--rows` caps the scan.

## Detector-input adapter (different contract)

`ushant.py` is **not** a loop-feature adapter — it does **not** emit the "last column =
target" contract above. It normalizes the Zenodo **Ushant AIS** dataset (Brittany,
France — Gloaguen et al. 2019; 18,603 per-vessel trajectory files, `"x";"y";"vx";"vy";"t"`,
`;`-delimited) into the **raw schema that `demo/ais_pol.py --csv` reads directly**:
`MMSI, LAT, LON, SOG, BaseDateTime` (ISO-8601).

Purpose: a **cross-region cold-start test** — run the unchanged `ais_pol` detector on a
totally different region/schema and prove the in-situ envelope generalizes. Honest
mapping: `SOG = sqrt(vx²+vy²)` (vx/vy already knots), x/y already decimal degrees
(no conversion); `t` is relative seconds → synthesized to ISO-8601 (only within-track
deltas matter to the detector); MMSI synthetic 1:1 from file index (dataset is
anonymized); `VesselType`/`Status` absent in source → omitted (loiter is therefore
suppressed). Output `data/datasets/ushant/ushant_normalized.csv` (gitignored, 427 MB).

```bash
python3 ingest/ushant.py
python3 demo/ais_pol.py --csv data/datasets/ushant/ushant_normalized.csv --rows 8000000
```

Full method + US-vs-Ushant numbers + verdict: **`docs/research/CROSS_REGION_VALIDATION.md`**.

## Contract reference
The data contract is documented in `demo/README.md` ("the three contracts"). `stage_data.py --input` validates by copying the CSV to `demo/data/staged.csv` and sealing a `data_staged` leaf (sha256 + rows) into the tamper-evident record. Rails honored: real data (sources stated), SWAN-side machinery + AIS only, human-in-command downstream.
