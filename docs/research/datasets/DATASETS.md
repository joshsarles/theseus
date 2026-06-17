# THESEUS — Open Dataset Brief
*Verified Jun 17 2026. Maritime Pattern-of-Life (NV063) + the engineering (PROP/PWR) + environmental organs. The two load-bearing sets (UCI naval propulsion, OMTAD) were fetch-verified; some arXiv/Kaggle slugs are agent-search and should be link-checked before proposal use.*

## TOP-5 — use these first
| # | Dataset | Organ | Why first |
|---|---------|-------|-----------|
| 1 | **UCI Condition-Based Maintenance of Naval Propulsion Plants** (`fetch_ucirepo(id=316)`) | PROP | **The bullseye.** Real frigate gas-turbine (CODLAG) decay data, labeled compressor + turbine decay targets. 554 KB, CC BY 4.0, one-line load. Trains the engineering organ end-to-end **today** — and it's tiny → ships to a Pi trivially. |
| 2 | **OMTAD** (+ Dec-2025 graph-anomaly benchmark) | NAV (NV063) | **Only open AIS dataset with explicit anomaly ground-truth** (node/edge/graph labels). 19,124 curated AMSA tracks. Directly supports explainable alerts. |
| 3 | **NOAA MarineCadastre US AIS** | NAV (NV063) | 25B+ points, decade span, fully open, US coastal. The "normal" PoL baseline; pair with OMTAD labels for train/eval. |
| 4 | **NASA C-MAPSS / N-CMAPSS turbofan** | PROP | Canonical labeled run-to-failure RUL benchmark; validates the degradation pipeline the small naval set can't alone. |
| 5 | **NASA IMS + CWRU bearing** | PWR | Rotating-machinery fault/RUL gold standards (IMS = run-to-failure trajectories; CWRU = labeled fault classes). |

**Best AIS-anomaly dataset:** **OMTAD** (Edith Cowan Univ., AMSA-sourced; real curated tracks + node/edge/graph anomaly labels). Runner-up for controlled benchmarking: **Sandia maritime-trajectory-anomaly-detection** (synthetic injection on real tracks, HawaiiCoast_GT).
**Best naval-machinery dataset:** **UCI CBM of Naval Propulsion Plants (#316)** — 11,934 instances, 16 features, 2 targets (GT compressor + turbine decay), CC BY 4.0.

## Bucket 1 — NAV / Maritime Pattern-of-Life (NV063)
**Anomaly-labeled (rare — prioritize):** OMTAD (github.com/EdithCowan/OMTAD; benchmark arXiv 2512.20086 — node/edge/graph labels) · Sandia maritime-trajectory-anomaly-detection (real AIS + synthetic injection + HawaiiCoast_GT, Zenodo) · kinematic anomaly taxonomy (speed/course/turn/loiter — drives *explainability*: alert = "loitering," not just "anomaly") · SIAP (synthetic AIS w/ IUU/smuggling labels — training proxy).
**Unlabeled AIS (normal-baseline / unsupervised):** NOAA MarineCadastre (marinecadastre.gov/accessais, GeoParquet) · Danish DMA AIS (dma.dk) · Norwegian Kystverket/Barentswatch (Arctic + sat-AIS) · GeoTrackNet (probabilistic scorer + US/Brittany AIS) · Kaggle AIS mirrors.
**Dark-vessel / spoofing:** Global Fishing Watch dark-vessel corpus (3.7B AIS + Sentinel-1 radar + VIIRS; 55k+ AIS-disabling events — closest thing to real AIS+radar fusion labels; fishing-specific) · SeaSpoofFinder (GNSS-spoofing case studies).
**ADS-B (air picture):** OpenSky Network (opensky-network.org; `pyopensky`; global 2013–present; registration for bulk). Use for ship↔aircraft cross-correlation.
**Radar / fusion (weakest area):** Autoferry sensor-fusion benchmark (synced radar+lidar+EO/IR+GT, littoral, only 3 scenarios) · CSIR/Fynmeet X-band sea-clutter (radar-only; use to *simulate* shipboard radar from AIS geometry). **No open AIS+radar+ADS-B fusion PoL dataset exists → synthesize the radar layer from AIS geometry.**

## Bucket 2 — PROP / PWR (machinery & CBM)
- **UCI Naval Propulsion Plants (#316)** — PROP bullseye (above).
- **NASA C-MAPSS / N-CMAPSS** — turbofan run-to-failure, RUL labels (NASA PCoE / Kaggle).
- **NASA IMS (Rexnord) bearing** — 4-bearing run-to-failure, 20 kHz vibration (NASA PCoE / data.nasa.gov).
- **CWRU bearing** — labeled fault classes, 12/48 kHz (engineering.case.edu/bearingdatacenter). *(Already on the portal.)*
- **FEMTO-ST/PRONOSTIA** bearing accelerated-life (RUL). **MaFaulDa / Paderborn / XJTU-SY** (good sets — locate clean URLs before relying). **MIMII** (machine-sound CBM — acoustic angle for PWR).
- *No open ship SCADA/engine telemetry exists (proprietary) — UCI #316 is the only ship-specific open set; everything else is transfer-learning from industrial analogs.*

## Bucket 3 — Environmental context (secondary; team already has some)
SST: NOAA OISST v2.1, Coral Reef Watch, GHRSST. Currents/waves: NDBC buoys, WaveWatch III, **HYCOM (Navy GOFS 3.1 — most ship-relevant)**, Copernicus/CMEMS (free reg). Cyclones: NOAA **IBTrACS**, NHC HURDAT2. Reanalysis: ECMWF **ERA5** (free reg). Access layer: NOAA **ERDDAP**.

## Caveats for the build / proposal
1. **Anomaly ground-truth is the scarce resource** — only OMTAD + Sandia (synthetic-injected) + the kinematic taxonomy give labels. Plan: **unsupervised train on MarineCadastre → labeled eval on OMTAD/Sandia** + expert-tagged navy anomalies.
2. **No real naval PoL benchmark** — all open AIS is commercial/fishing; navy-specific anomalies need expert annotation or simulation.
3. **No open AIS+radar+ADS-B fusion set** — synthesize radar from AIS geometry, cross-correlate OpenSky ADS-B, GFW is the closest real multi-modal label source.
4. **PROP organ is best-served** — UCI #316 + C-MAPSS/IMS/CWRU = a mature labeled stack.

## Recommended for the Warhacker demo
- **PROP model on the Pi:** train a gas-turbine decay/RUL model on **UCI #316** (tiny, real, naval, labeled) → deploy via MLflow to the Pi cluster → demo live model update + shore-staged version push. *This is the cleanest "real model on the edge" beat with genuinely naval data.*
- **NAV/anomaly model:** unsupervised PoL on **MarineCadastre** AIS, eval against **OMTAD** labels, live **AIS via SDR** at the venue → explainable "loitering/dark/off-baseline" alert → maps to **NV063**.
