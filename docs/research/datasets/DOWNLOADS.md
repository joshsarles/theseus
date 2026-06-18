# THESEUS — Downloaded Datasets (manifest)

*What is physically on disk in this repo, why it's here, and how to reproduce it. Companion to `DATASETS.md` (the full catalog).*

## Where the data lives + the rule
- **Local path:** `data/datasets/` (repo working tree).
- **`data/` is gitignored** (`.gitignore:13`). The dataset bytes are **NOT committed** and never will be — per `CONTRIBUTING.md` (no dataset files in git) and to avoid any license-redistribution exposure on this AGPL/public repo. This manifest is the only committed record.
- **Only Tier-1 commercial-clean / public-domain sets were pulled** (see `DATASETS.md §2`). No NON-COMMERCIAL or license-unstated set was downloaded into the tree (rationale below).
- Total on disk: **~19.7 GB** (incl. the retained 14.7 GB N-CMAPSS source archive + 2.45 GB extracted DS02; the rest ~2.2 GB).

## On disk now

| Dataset | Local path | License (commercial-OK) | Source | Integrity | Extracted contents |
|---|---|---|---|---|---|
| **UCI #316 — CBM of Naval Propulsion Plants** | `data/datasets/cbm_naval_316/` | **CC BY 4.0 ✅** | https://archive.ics.uci.edu/dataset/316 | zip sha256 `91a3815d…3cb9` (554 KB) | `UCI CBM Dataset/{data.txt, Features.txt, README.txt}` — 16-feature frigate GT vector + compressor/turbine decay labels. **SWAN-side machinery bullseye.** |
| **UCI #791 — MetroPT-3 (air compressor)** | `data/datasets/metropt3/` | **CC BY 4.0 ✅** | https://archive.ics.uci.edu/dataset/791 | zip sha256 `aab991a9…721a` (208 MB) | `MetroPT3(AirCompressor).csv` (770 MB unzip, ~1.5M rows, 1 Hz) + `Data Description_Metro.pdf`. **Real operational compressor/pneumatic telemetry.** |
| **NASA C-MAPSS — turbofan degradation** | `data/datasets/cmapss/` | **US-Gov public ✅** (citation requested) | mirror github.com/edwardzjl/CMAPSSData @ `ed40e40` (NASA PCoE origin) | git clone (56 MB) | `train/test/RUL_FD00{1..4}.txt` + `readme.txt`. **GT RUL benchmark.** |
| **N-CMAPSS — Turbofan Degradation Sim Data Set 2 (DS02)** | `data/datasets/ncmapss/` | **US-Gov public ✅** (citation requested) | NASA PCoE via PHM S3 mirror: `phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip` (14.7 GB; nested `data_set.zip` → `N-CMAPSS_DS0{1..8}.h5`) | ✅ **on disk** — `N-CMAPSS_DS02-006.h5` (2.45 GB) sha256 `47971a68b239ecb756833218a95d68ded6eb7e63ee84e86671c8b188de1ca765`; 14.7 GB source zip retained | **Realistic full-flight successor to C-MAPSS** (real flight envelopes, run-to-failure). Adapter `ingest/ncmapss.py` **validated on real DS02**: dev → 52,635 rows × 19 (18 feats + `rul`), units 2,5,10,16,18,20 (`--stride 100`). |
| **Ushant (Brest TSS) AIS** | `data/datasets/ushant/` | **CC BY 4.0 ✅** (figshare-confirmed) | figshare 8966273 → file 16442771 | zip sha256 `10188077…fe43` (125 MB) | `data/` (18,605 per-trajectory files, 509 MB) + `READ_ME.html`. **Clean AIS Pattern-of-Life baseline.** |
| **TrAISformer `ct_dma`** | `data/datasets/traisformer/` | code **CeCILL-C** (commercial-OK, copyleft on code mods); data DMA-derived (open) | github.com/CIA-Oceanix/TrAISformer | git clone (75 MB) | `data/ct_dma/{train 36M, test 5.9M, valid 5.2M, coastline}.pkl`. **NV061 SOTA trajectory baseline + ready model code.** |
| **MarineCadastre US AIS — 2024-01-01 daily** | `data/datasets/marinecadastre_us/` | **US-Gov public domain ✅** | https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/AIS_2024_01_01.zip | zip sha256 `03ed1e16…253c` (277 MB) | `AIS_2024_01_01.csv` (770 MB, **7,296,276 rows**, full AIS schema). **Congested US-coastal volume (NV063 condition); 1-day representative sample.** |

## Reproduce (any machine)
```bash
mkdir -p data/datasets && cd data/datasets
# UCI CBM Naval (CC BY 4.0)
curl -L -o cbm_naval_316.zip "https://archive.ics.uci.edu/static/public/316/condition+based+maintenance+of+naval+propulsion+plants.zip" && unzip -o cbm_naval_316.zip -d cbm_naval_316
# MetroPT-3 (CC BY 4.0)
curl -L -o metropt3_791.zip "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip" && unzip -o metropt3_791.zip -d metropt3
# NASA C-MAPSS (US-Gov)
git clone --depth 1 https://github.com/edwardzjl/CMAPSSData cmapss
# N-CMAPSS / Turbofan Degradation Sim Data Set 2 (US-Gov) — 14.7 GB archive with a NESTED data_set.zip; macOS unzip can't read the >4 GB Zip64, so use Python:
mkdir -p ncmapss && curl -L --fail -o ncmapss/ncmapss_nasa.zip "https://phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip"
python3 - <<'PY'
import zipfile, shutil, os
o = zipfile.ZipFile("ncmapss/ncmapss_nasa.zip")
inner = [n for n in o.namelist() if n.endswith("data_set.zip")][0]
with o.open(inner) as s, open("ncmapss/data_set.zip","wb") as d: shutil.copyfileobj(s, d, 1<<25)
z = zipfile.ZipFile("ncmapss/data_set.zip")
m = [n for n in z.namelist() if "DS02-006" in n and n.endswith(".h5")][0]
with z.open(m) as s, open("ncmapss/N-CMAPSS_DS02-006.h5","wb") as d: shutil.copyfileobj(s, d, 1<<25)
os.remove("ncmapss/data_set.zip")
PY
# then, from repo root: python3 ingest/ncmapss.py --stride 100
# Ushant AIS (CC BY 4.0)
curl -L -o ushant_ais.zip "https://ndownloader.figshare.com/files/16442771" && unzip -o ushant_ais.zip -d ushant
# TrAISformer ct_dma (CeCILL-C code)
git clone --depth 1 https://github.com/CIA-Oceanix/TrAISformer traisformer
# MarineCadastre US AIS 1-day sample (public domain)
curl -L -o ais_us_2024_01_01.zip "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/AIS_2024_01_01.zip" && unzip -o ais_us_2024_01_01.zip -d marinecadastre_us
find . -name __MACOSX -type d -prune -exec rm -rf {} +
```

## Deliberately NOT downloaded (and why)
- **NON-COMMERCIAL / research-only** (would violate license to bundle, or pollute the tree): Global Fishing Watch (CC BY-NC-SA), **Piraeus AIS** (license conflict → treated NC until confirmed), MASATI, ViCoS MaSTr1325/MODD/MODS, MIMII (CC BY-SA copyleft), CWRU/MAFAULDA/FEMTO/PHM (license-unstated), all license-unstated SAR sets (OpenSARShip, FUSAR, SSDD, HRSID…), IPIX, SMD, SeaShips, OpenSky.
- **Gated / access-by-request:** Reading iPatch (AIS+radar+EO/IR — email authors), CSIR Fynmeet, the CN SAR portals.
- **Commercial-clean but deferred (optional, easy to add later):** Mendeley GPS-spoofing UAS (CC BY 4.0, 247 MB), TartanAviation (CC BY 4.0, large), additional MarineCadastre days/zones, Copernicus Sentinel-1 SAR (free, attribution).
- **Tooling (install, not download):** AIS-catcher / dump1090-fa (SDR own-capture), Stone Soup, MSS, pyais, OpenDDS — pulled at build time, not dataset artifacts.

## Verify integrity
```bash
cd data/datasets && shasum -a 256 *.zip   # compare against the sha256 column above
```
