# THESEUS — Open Dataset Master Catalog

*Synthesis of the 6-category discovery fleet (Jun 17 2026). Source-of-truth index; per-category depth lives in `A_…`–`F_…_REPORT.md` beside this file. **LICENSE-FIRST** (we ship a product + a for-profit SBIR — commercial-use suitability gates every row). **HONESTY-FIRST** (verified vs UNVERIFIED labeled; gaps called out, not papered over).*

THESEUS = airgapped, tamper-evident onboard maritime decision-support substrate. Build beats the data serves: **SCREEN → CORRELATE** (AIS+ADS-B+radar into one picture) · **DETECT** cold-start Pattern-of-Life anomaly (no historical DB; novel areas) · **PREDICT** object trajectory (NV061) · **SWAN-side** machinery/HM&E health · **PROVE** (record is the moat; data is the input).

---

## §1 — Bottom line up front

1. **There is a clean commercial-OK spine** for the whole build: **MarineCadastre AIS** (US public domain), **Ushant TSS AIS** (CC BY 4.0), **UCI CBM Naval Propulsion** + **MetroPT-3** + **NASA C-MAPSS** (machinery), **TrAISformer `ct_dma`** (trajectory baseline), and the **MIT/Apache tool layer** (MSS sim, Stone Soup fusion, pyais, OpenDDS, SDR capture). You can build, train, demo, and deliver an SBIR on these without a licensing landmine.
2. **The cold-start story is physical, not theoretical.** A ~$30 RTL-SDR on a Raspberry Pi (AIS-catcher + dump1090-fa) has THESEUS **generating its own real, live AIS + ADS-B picture, fully airgapped** — the Warhacker money shot and the honest answer to "no historical DB." Receive-only, legal (NAVCEN: only *transmitting* AIS stations are restricted).
3. **Three honest gaps** (mitigations in §5): (a) **no open dataset co-registers AIS+ADS-B+radar** — we synthesize/self-fuse; (b) **no open in-situ naval HM&E telemetry** — we transfer from sim-naval + real-adjacent; (c) **no open *naval* trajectory benchmark** — we use commercial AIS-TP + simulate naval maneuvers.
4. **Licenses verified (Jun 17).** **Piraeus AIS is CC BY 4.0 — commercial-OK** (the earlier conflict was cross-contamination with Brest/Ray-2019, which genuinely *is* CC BY-NC-SA / non-commercial — as is **xView3-SAR**). **DMA** is open under the Danish PSI Act (commercial-OK). **OpenSky** is research/non-profit only (for-profit + gov/military contractors need a written license; §6 joint-IP). See §2 / §6.
5. **Every cloud feed is a shore/build-time seed only.** Copernicus, GFW, OpenSky, aisstream cannot reach an airgapped ship — they train the cold-start model ashore; own-capture sustains it underway. Design for that.

---

## §2 — License tiers (THE decision axis)

| Tier | Meaning | Datasets / resources |
|---|---|---|
| **TIER 1 — COMMERCIAL-CLEAN** (ship in product + SBIR) | Public-domain or permissive (US-Gov / CC BY / MIT / Apache / NLOD / PSI-Act) | **AIS:** MarineCadastre (US, public domain) · Ushant/Brest-TSS figshare (CC BY 4.0) · **Piraeus AIS (CC BY 4.0 — confirmed Jun 17)** · Kystverket Norway (NLOD) · DMA Denmark (open, Danish PSI Act) · **Machinery:** UCI CBM Naval Propulsion (CC BY 4.0) · MetroPT-3 (CC BY 4.0) · NASA C-MAPSS + **N-CMAPSS** + IMS (US-Gov) · **Air:** TartanAviation (CC BY 4.0) · Mendeley GPS-Spoofing (CC BY 4.0) · **Tools/sim:** MSS (MIT) · Stone Soup (MIT) · pyais (MIT) · OpenDDS (permissive) · AISonobuoy (Apache-2.0) · SDR capture AIS-catcher/rtl-ais/dump1090-fa (GPL, **standalone sidecar only — never static-link**) · **Env/standards:** Copernicus CMEMS + Sentinel-1 (free, attribution; shore-seed) · EMODnet · US Navigation Rules/33 CFR COLREGs (public domain) · UMAA Distro-A + Naval-MOSA guidebook (US-Gov) |
| **TIER 2 — COMMERCIAL-OK *IF* LICENSED** | Paid tier or copyleft-on-code | ADS-B Exchange (paid commercial; **has military aircraft**) · airplanes.live (commercial contact; free tier NC) · TrAISformer code (CeCILL-C: commercial-OK, copyleft on *code* mods only) |
| **TIER 3 — RESEARCH-ONLY / NON-COMMERCIAL / UNSTATED** (R&D enclave; **never** in a shipped/delivered artifact without written permission) | NC license, copyleft-data, or no license posted | **Brest/Ray-2019** (CC BY-NC-SA 4.0 — confirmed Jun 17; the genuine NC AIS set) · **xView3-SAR** (CC BY-NC-SA 4.0, DIU xView program standard — confirmed Jun 17) · **OpenSky Network** (research/non-profit only; for-profit + gov/military contractors need a written license; §6 joint-IP; gov-purposes exemption discretionary, NOT automatic for a for-profit SBIR) · **Global Fishing Watch** (CC BY-NC-SA; *best dark-vessel labels* but NC) · MASATI (NC + Bing terms) · ViCoS MaSTr1325/MODD/MODS (CC BY-NC-SA likely) · MIMII (CC BY-SA copyleft trap) · CWRU / MAFAULDA / FEMTO-PRONOSTIA / PHM-Society challenges (license unstated) · OpenSARShip / FUSAR-Ship / SSDD / LS-SSDD / HRSID / SAR-Ship-Dataset / AIR-SARShip (license unstated → research-only) · IPIX (cite + keep-informed) · SMD / SeaShips (research-use) · AISHub (reciprocal, no-redistribution) · OMTAD (license UNVERIFIED) · MOOS-IvP (GPLv3 + academic-use nuance) |
| **GATED / ACCESS-UNCONFIRMED** (request from authors; do not assume a download) | — | **Reading "iPatch"** (restricted PDF — *best on-paper AIS+radar+EO/IR fit*, email Ferryman/Reading) · **CSIR Fynmeet** sea-clutter (request from CSIR) · OpenSARShip/FUSAR-Ship (CN portal registration) |

> **Licenses resolved Jun 17 (was "verify-before-SBIR"):** Piraeus = **CC BY 4.0, commercial-OK** (both Zenodo records 6323416 + 5562629); Brest/Ray-2019 = **CC BY-NC-SA 4.0** (research-only); xView3-SAR = **CC BY-NC-SA 4.0** (research-only); DMA = **open, Danish PSI Act** (commercial-OK, no-warranty + no-re-identification conditions); OpenSky = **research/non-profit only** (contractors/product need a written license; §6 joint-IP).

---

## §3 — By build beat (what to use for what)

| Beat | Primary (commercial-clean) | Supplemental (research-only / gated) |
|---|---|---|
| **SCREEN + CORRELATE** (living AIS picture) | MarineCadastre · Ushant · **Piraeus (CC BY 4.0, dense-port)** · Kystverket · DMA · **own-capture** (AIS-catcher/dump1090-fa) | AISHub (live proto only) |
| **DETECT — cold-start anomaly (NV063)** | Synthesize lane/gap/spoof anomalies on Ushant + MarineCadastre · Mendeley GPS-spoofing (CC BY) | xView3-SAR (CC BY-NC-SA, dark-vessel) · GFW dark-vessel/loitering labels (NC, eval-only) · OMTAD/NeurIPS'25 graph benchmark (verify) · OpenSARShip/FUSAR (AIS↔radar matchup, gated) |
| **PREDICT — trajectory (NV061)** | **TrAISformer `ct_dma`** (SOTA baseline) · isaacOnline/ships harness · **CV/CTRV/Kalman floor** (the real bar) · conformal wrapper for calibrated intervals | Brest/Ray-2019 (env-aware; **CC BY-NC-SA, research-only**) · **EnvShip-Bench** (arXiv 2606.15240, Jun 2026; forecast-ready env-aware NV061 benchmark — code MIT, HF data from DMA+NOAA; eval-OK) |
| **SWAN-side machinery / HM&E** | **UCI CBM Naval Propulsion** (frigate GT — bullseye) · **MetroPT-3** (real compressor/pneumatic) · NASA C-MAPSS + IMS (GT RUL) | CWRU/FEMTO/MAFAULDA (bearings, license-unstated) · MIMII (acoustic, copyleft) |
| **RADAR-SIGNAL layer** (clutter/CFAR) | — (no commercial-clean open radar-I/Q found) | IPIX (research) · CSIR Fynmeet (gated) · MOANA (shipborne X-band; verify) |
| **EO/IR camera channel** (explainability, vessel-class priors) | TartanAviation (air, CC BY — fusion template) | SMD · SeaShips · ViCoS (NC) · MASATI (NC) |
| **FUSION-SYNTH** (fills the AIS+radar+ADS-B gap) | **Stone Soup** (synth multi-sensor detections + ground truth) · **MSS** (vessel kinematics + sea state) | MOOS-IvP (COLREG-compliant traffic; GPL) |

---

## §4 — Warhacker demo data plan (actionable now, mid-event)

1. **Own-capture rig (the cold-start centerpiece):** RTL-SDR + Raspberry Pi running **AIS-catcher** (real ships) and **dump1090-fa** (real aircraft) → THESEUS fuses a live, real, airgapped AIS+ADS-B picture with zero cloud and no historical DB. `pyais` decodes NMEA into the ingest schema. This is the visceral "generates its own real data" beat. Build guide: `docs/research/SDR_CAPTURE_PLAN.md`.
2. **Replay/train (commercial-clean):** MarineCadastre + Ushant for AIS volume + a clean Pattern-of-Life baseline; UCI CBM Naval + MetroPT-3 for the SWAN-side machinery anomaly beat. Normalized to the loop contract by `ingest/` adapters → `ingest/out/<name>.csv`.
3. **Fusion + radar where no real data exists:** Stone Soup synthesizes co-registered radar/EO/AIS detections + ground truth; MSS adds physically-real vessel kinematics / sea-state perturbation.
4. **Anomaly eval:** synthesize lane-violation / AIS-gap / spoof anomalies on Ushant + MarineCadastre (commercial-clean); use GFW dark-vessel labels for **internal validation only**; chase OMTAD for a labeled NV063 eval if its license clears. Scoring via `eval/score.py` (precision/recall/false-alarm rate).
5. **Integration credibility:** frame interfaces on **UMAA Distro-A ICDs over OpenDDS**, cite **Naval-MOSA**; COLREGs reasoning off the public-domain **US Navigation Rules**.

---

## §5 — The honest gaps (HONESTY-FIRST) + mitigations

1. **No open dataset co-registers AIS + ADS-B + radar on one frame.** → Build fusion ground-truth ourselves: time/space-align a Category-A AIS source with a Category-B ADS-B source, and use **Stone Soup** to synthesize multi-sensor detections + truth. **TartanAviation** is the closest methodological template (track↔sensor projection) but is air-only. *Treat fusion GT as a build item, not a download.*
2. **No open in-situ naval shipboard HM&E telemetry** (navy/shipowner proprietary). → **UCI CBM Naval** (sim-naval frigate GT) + **MetroPT-3** (real operational compressor/pneumatic) + **NASA C-MAPSS** (GT RUL), then domain-transfer. Flag this to the SBIR/product team early; the real-feed path is the Red-Team's "name one real ship-data feed" gate.
3. **No open *naval* trajectory-prediction benchmark** (all open AIS-TP is commercial/fishing traffic). → **TrAISformer `ct_dma`** + **Brest** for the baseline; **simulate naval maneuvers** (evasion, formation, sensor-cued intercept) with MSS / MOOS-IvP for the naval-specific eval. Always report gain vs the **CV/Kalman** floor.
4. **Cold-start runtime reality:** cloud feeds (Copernicus, GFW, OpenSky, aisstream) are **shore/build-time seeds only** — none reach an airgapped ship. Runtime data path at sea = **own SDR capture + onboard sensors**. Architecture must reflect this (train ashore, sustain underway).
5. **No commercial-clean open radar-signal (I/Q) set** — IPIX/CSIR/MOANA are research/gated. The radar-signal/CFAR layer leans on those for *algorithm* dev; the shippable radar story rides synthetic (Stone Soup) + the live onboard feed.

---

## §6 — Action checklist

**Pulled to disk (commercial-clean, in `data/datasets/`, gitignored — see `DOWNLOADS.md`):** MarineCadastre AIS (1-day) · Ushant TSS · UCI CBM Naval · MetroPT-3 · NASA C-MAPSS · TrAISformer `ct_dma`. Normalized to the loop contract by `ingest/` adapters.

**Consider next (Jun 17 deep-search delta):**
- **N-CMAPSS** (Turbofan Degradation Simulation Data Set 2) — commercial-clean (US-Gov), the **realistic full-flight-condition successor to C-MAPSS**; strict upgrade for the RUL/degradation validation beat (warship GT runs across varying operating points, not one steady state). → **Pulling now** (14.7 GB NASA archive, background; extract `N-CMAPSS_DS02-006.h5`) + **adapter `ingest/ncmapss.py` built & fixture-validated** (`python3 ingest/ncmapss.py --stride 100`). Detail in `D_SHIP_MACHINERY_CBM_REPORT.md` + `DOWNLOADS.md`.
- **EnvShip-Bench** (arXiv 2606.15240, Jun 13 2026) — **resolved Jun 17**: code **MIT**, data on **HuggingFace** (forecast-ready CSV shards + compact `clean_ship_core_lite_v1` + env/social context), built from **DMA + NOAA** (commercial-clean provenance; no explicit data-license tag → eval-first, regenerate from the MIT pipeline for delivered use). Strong NV061 eval target. Detail in `E_TRAJECTORY_PREDICTION_REPORT.md`.
- Everything else surfaced by the re-search (XJTU-SY / Paderborn bearings, IEEE-DataPort synthetic-spoofing, PHM survey arXiv 2403.13694, `awesome-*` dataset indices) is **already cataloged or same-tier** (research/license-unclear) — no commercial-clean upgrade over the current spine.

**Licenses RESOLVED (Jun 17 verification — primary-source confirmed):**
- **Piraeus AIS** — **CC BY 4.0, commercial-OK** (Zenodo records 6323416 + 5562629; license field `cc-by-4.0`). The earlier "CC BY-NC-SA" reading was cross-contamination with Brest/Ray-2019. → promoted to Tier 1.
- **Brest/Ray-2019** — **CC BY-NC-SA 4.0** (Zenodo 1167595), NON-COMMERCIAL / research-only. → Tier 3.
- **DMA Denmark** — open under the **Danish PSI Act** (Act 596/2005); historical bulk AIS free + commercial re-use permitted. Conditions: no warranty; no combining data to re-identify persons.
- **xView3-SAR** — **CC BY-NC-SA 4.0** (DIU xView program standard), NON-COMMERCIAL. (Gated T&C verbatim string still to capture behind login, but the program-standard license is unambiguous.)
- **OpenSky** — **research/non-profit only**; *"any use by a for-profit or commercial entity requires written permission"* and **explicitly names government/military contractors**; §6 makes commercially-developed IP joint property absent a written exemption. Research/eval only; never product-embed.

**Request access (gated, worth it):** Reading iPatch (AIS+radar+EO/IR — email Ferryman/Reading) · CSIR Fynmeet · OpenSARShip + FUSAR-Ship (CN portals).

**Keep in the R&D enclave, NEVER in a deliverable (NC / unstated):** Global Fishing Watch · **Brest/Ray-2019 (CC BY-NC-SA)** · **xView3-SAR (CC BY-NC-SA)** · OpenSky · MASATI · ViCoS · MIMII · CWRU/MAFAULDA/FEMTO/PHM · all license-unstated SAR sets · IPIX/SMD/SeaShips.

---

## §7 — Category reports (depth) + lane artifacts
- `A_AIS_MARITIME_REPORT.md` — AIS trajectory + Pattern-of-Life + anomaly benchmarks
- `B_AIR_ADSB_REPORT.md` — ADS-B + AIS↔ADS-B fusion (incl. military-aircraft sources)
- `C_RADAR_EOIR_SAR_REPORT.md` — marine radar/sea-clutter + EO/IR + SAR ship detection + maritime MOT
- `D_SHIP_MACHINERY_CBM_REPORT.md` — SWAN-side HM&E / condition-based + predictive maintenance
- `E_TRAJECTORY_PREDICTION_REPORT.md` — vessel/maritime trajectory forecasting (NV061)
- `F_SIM_SYNTH_STANDARDS_REPORT.md` — simulators + synthetic generators + gov feeds + standards
- `DOWNLOADS.md` — what's pulled to disk (sources + licenses + sha256)
- `../SDR_CAPTURE_PLAN.md` — own-capture rig (AIS-catcher + dump1090-fa on a Pi)
- `../../../ingest/` — dataset→loop-contract adapters · `../../../eval/` — NV063 anomaly scorer · `../../../models/nv061/` — TrAISformer trajectory baseline
