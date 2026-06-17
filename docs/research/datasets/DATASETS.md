# THESEUS — Open Dataset Master Catalog

*Synthesis of the 6-category discovery fleet (Jun 17 2026). Source-of-truth index; per-category depth lives in `A_…`–`F_…_REPORT.md` beside this file. **LICENSE-FIRST** (we ship a product + a for-profit SBIR — commercial-use suitability gates every row). **HONESTY-FIRST** (verified vs UNVERIFIED labeled; gaps called out, not papered over).*

THESEUS = airgapped, tamper-evident onboard maritime decision-support substrate. Build beats the data serves: **SCREEN → CORRELATE** (AIS+ADS-B+radar into one picture) · **DETECT** cold-start Pattern-of-Life anomaly (no historical DB; novel areas) · **PREDICT** object trajectory (NV061) · **SWAN-side** machinery/HM&E health · **PROVE** (record is the moat; data is the input).

---

## §1 — Bottom line up front

1. **There is a clean commercial-OK spine** for the whole build: **MarineCadastre AIS** (US public domain), **Ushant TSS AIS** (CC BY 4.0), **UCI CBM Naval Propulsion** + **MetroPT-3** + **NASA C-MAPSS** (machinery), **TrAISformer `ct_dma`** (trajectory baseline), and the **MIT/Apache tool layer** (MSS sim, Stone Soup fusion, pyais, OpenDDS, SDR capture). You can build, train, demo, and deliver an SBIR on these without a licensing landmine.
2. **The cold-start story is physical, not theoretical.** A ~$30 RTL-SDR on a Raspberry Pi (AIS-catcher + dump1090-fa) has THESEUS **generating its own real, live AIS + ADS-B picture, fully airgapped** — the Warhacker money shot and the honest answer to "no historical DB." Receive-only, legal (NAVCEN: only *transmitting* AIS stations are restricted).
3. **Three honest gaps** (mitigations in §5): (a) **no open dataset co-registers AIS+ADS-B+radar** — we synthesize/self-fuse; (b) **no open in-situ naval HM&E telemetry** — we transfer from sim-naval + real-adjacent; (c) **no open *naval* trajectory benchmark** — we use commercial AIS-TP + simulate naval maneuvers.
4. **One license conflict to resolve before anything ships → Piraeus AIS** (see §2 / §6). Treat as **NON-COMMERCIAL until confirmed.**
5. **Every cloud feed is a shore/build-time seed only.** Copernicus, GFW, OpenSky, aisstream cannot reach an airgapped ship — they train the cold-start model ashore; own-capture sustains it underway. Design for that.

---

## §2 — License tiers (THE decision axis)

| Tier | Meaning | Datasets / resources |
|---|---|---|
| **TIER 1 — COMMERCIAL-CLEAN** (ship in product + SBIR) | Public-domain or permissive (US-Gov / CC BY / MIT / Apache / NLOD) | **AIS:** MarineCadastre (US, public domain) · Ushant/Brest-TSS figshare (CC BY 4.0) · Kystverket Norway (NLOD) · DMA Denmark (free/open — confirm policy string) · **Machinery:** UCI CBM Naval Propulsion (CC BY 4.0) · MetroPT-3 (CC BY 4.0) · NASA C-MAPSS + IMS (US-Gov) · **Air:** TartanAviation (CC BY 4.0) · Mendeley GPS-Spoofing (CC BY 4.0) · **Tools/sim:** MSS (MIT) · Stone Soup (MIT) · pyais (MIT) · OpenDDS (permissive) · AISonobuoy (Apache-2.0) · SDR capture AIS-catcher/rtl-ais/dump1090-fa (GPL, **standalone sidecar only — never static-link**) · **Env/standards:** Copernicus CMEMS + Sentinel-1 (free, attribution; shore-seed) · EMODnet · US Navigation Rules/33 CFR COLREGs (public domain) · UMAA Distro-A + Naval-MOSA guidebook (US-Gov) |
| **TIER 2 — COMMERCIAL-OK *IF* LICENSED / VERIFY** | Paid tier, copyleft-on-code, or license string unconfirmed | ADS-B Exchange (paid commercial; **has military aircraft**) · airplanes.live (commercial contact; free tier NC) · **xView3-SAR** (free-for-challenge; verify T&C — xView family historically NC) · **Brest/Ray-2019** Zenodo (reads "Open Access", exact CC tag not shown — VERIFY) · TrAISformer code (CeCILL-C: commercial-OK, copyleft on *code* mods only) |
| **TIER 3 — RESEARCH-ONLY / NON-COMMERCIAL / UNSTATED** (R&D enclave; **never** in a shipped/delivered artifact without written permission) | NC license, copyleft-data, or no license posted | **OpenSky Network** (research/gov/eval; §6 joint-IP clause — usable under SBIR "government-purposes" R&D, NOT product-embed) · **Global Fishing Watch** (CC BY-NC-SA; *best dark-vessel labels* but NC) · **Piraeus AIS** ⚠️ **CONFLICTING reads — treat NC until confirmed** · MASATI (NC + Bing terms) · ViCoS MaSTr1325/MODD/MODS (CC BY-NC-SA likely) · MIMII (CC BY-SA copyleft trap) · CWRU / MAFAULDA / FEMTO-PRONOSTIA / PHM-Society challenges (license unstated) · OpenSARShip / FUSAR-Ship / SSDD / LS-SSDD / HRSID / SAR-Ship-Dataset / AIR-SARShip (license unstated → research-only) · IPIX (cite + keep-informed) · SMD / SeaShips (research-use) · AISHub (reciprocal, no-redistribution) · OMTAD (license UNVERIFIED) · MOOS-IvP (GPLv3 + academic-use nuance) |
| **GATED / ACCESS-UNCONFIRMED** (request from authors; do not assume a download) | — | **Reading "iPatch"** (restricted PDF — *best on-paper AIS+radar+EO/IR fit*, email Ferryman/Reading) · **CSIR Fynmeet** sea-clutter (request from CSIR) · OpenSARShip/FUSAR-Ship (CN portal registration) |

> **⚠️ Piraeus conflict (resolve first):** Category-A read CC BY 4.0; Category-E read CC BY-NC-SA 4.0. Until the Zenodo license field is confirmed, **Piraeus is research/eval-only** and firewalled from any deliverable.

---

## §3 — By build beat (what to use for what)

| Beat | Primary (commercial-clean) | Supplemental (research-only / gated) |
|---|---|---|
| **SCREEN + CORRELATE** (living AIS picture) | MarineCadastre · Ushant · Kystverket · DMA · **own-capture** (AIS-catcher/dump1090-fa) | Piraeus* (dense-port, NC), AISHub (live proto only) |
| **DETECT — cold-start anomaly (NV063)** | Synthesize lane/gap/spoof anomalies on Ushant + MarineCadastre · Mendeley GPS-spoofing (CC BY) · xView3-SAR† (dark-vessel) | GFW dark-vessel/loitering labels (NC, eval-only) · OMTAD/NeurIPS'25 graph benchmark (verify) · OpenSARShip/FUSAR (AIS↔radar matchup, gated) |
| **PREDICT — trajectory (NV061)** | **TrAISformer `ct_dma`** (SOTA baseline) · isaacOnline/ships harness · **CV/CTRV/Kalman floor** (the real bar) · conformal wrapper for calibrated intervals | Brest/Ray-2019 (env-aware; license VERIFY) · Piraeus* (dense, NC) |
| **SWAN-side machinery / HM&E** | **UCI CBM Naval Propulsion** (frigate GT — bullseye) · **MetroPT-3** (real compressor/pneumatic) · NASA C-MAPSS + IMS (GT RUL) | CWRU/FEMTO/MAFAULDA (bearings, license-unstated) · MIMII (acoustic, copyleft) |
| **RADAR-SIGNAL layer** (clutter/CFAR) | — (no commercial-clean open radar-I/Q found) | IPIX (research) · CSIR Fynmeet (gated) · MOANA (shipborne X-band; verify) |
| **EO/IR camera channel** (explainability, vessel-class priors) | TartanAviation (air, CC BY — fusion template) | SMD · SeaShips · ViCoS (NC) · MASATI (NC) |
| **FUSION-SYNTH** (fills the AIS+radar+ADS-B gap) | **Stone Soup** (synth multi-sensor detections + ground truth) · **MSS** (vessel kinematics + sea state) | MOOS-IvP (COLREG-compliant traffic; GPL) |

\* Piraeus = NC until license confirmed.  † xView3 = verify T&C before deliverable.

---

## §4 — Warhacker demo data plan (actionable now, mid-event)

1. **Own-capture rig (the cold-start centerpiece):** RTL-SDR + Raspberry Pi running **AIS-catcher** (real ships) and **dump1090-fa** (real aircraft) → THESEUS fuses a live, real, airgapped AIS+ADS-B picture with zero cloud and no historical DB. `pyais` decodes NMEA into the ingest schema. This is the visceral "generates its own real data" beat.
2. **Replay/train (commercial-clean):** MarineCadastre + Ushant for AIS volume + a clean Pattern-of-Life baseline; UCI CBM Naval + MetroPT-3 for the SWAN-side machinery anomaly beat.
3. **Fusion + radar where no real data exists:** Stone Soup synthesizes co-registered radar/EO/AIS detections + ground truth; MSS adds physically-real vessel kinematics / sea-state perturbation.
4. **Anomaly eval:** synthesize lane-violation / AIS-gap / spoof anomalies on Ushant + MarineCadastre (commercial-clean); use GFW dark-vessel labels for **internal validation only**; chase OMTAD for a labeled NV063 eval if its license clears.
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

**Pull now (commercial-clean, zero-risk):** MarineCadastre AIS · Ushant TSS (figshare) · UCI CBM Naval (`ucimlrepo id=316`) · MetroPT-3 (UCI #791) · NASA C-MAPSS (PHM mirror) · TartanAviation · Mendeley GPS-spoofing · MSS · Stone Soup · pyais · OpenDDS · SDR tooling (AIS-catcher/dump1090-fa).

**License-clear BEFORE it enters the SBIR compliance file / product:**
- **Piraeus AIS** — resolve the CC BY 4.0 vs CC BY-NC-SA conflict (Zenodo license field). *Conservative = NC.*
- **Brest/Ray-2019** — confirm exact Zenodo CC tag.
- **DMA Denmark** — capture the exact reuse string from the data-management-policy page.
- **xView3-SAR** — read challenge T&C for commercial/SBIR redistribution.
- **OpenSky** — legal read on the §6 joint-IP clause; confine to SBIR "government-purposes" R&D, never product-embed.

**Request access (gated, worth it):** Reading iPatch (AIS+radar+EO/IR — email Ferryman/Reading) · CSIR Fynmeet · OpenSARShip + FUSAR-Ship (CN portals).

**Keep in the R&D enclave, NEVER in a deliverable (NC / unstated):** Global Fishing Watch · Piraeus (until cleared) · MASATI · ViCoS · MIMII · CWRU/MAFAULDA/FEMTO/PHM · all license-unstated SAR sets · IPIX/SMD/SeaShips.

---

## §7 — Category reports (depth)
- `A_AIS_MARITIME_REPORT.md` — AIS trajectory + Pattern-of-Life + anomaly benchmarks
- `B_AIR_ADSB_REPORT.md` — ADS-B + AIS↔ADS-B fusion (incl. military-aircraft sources)
- `C_RADAR_EOIR_SAR_REPORT.md` — marine radar/sea-clutter + EO/IR + SAR ship detection + maritime MOT
- `D_SHIP_MACHINERY_CBM_REPORT.md` — SWAN-side HM&E / condition-based + predictive maintenance
- `E_TRAJECTORY_PREDICTION_REPORT.md` — vessel/maritime trajectory forecasting (NV061)
- `F_SIM_SYNTH_STANDARDS_REPORT.md` — simulators + synthetic generators + gov feeds + standards
