# THESEUS — Open Dataset Hunt (ROADMAP / source of truth)

**Mission:** find every relevant open-source / open-access dataset THESEUS can use to build, train, and benchmark the maritime ship-brain — and prove the NV063 / NV061 SBIR cold-start architecture. Mid-event (Jun 17 2026); team is building, this lane feeds them data.

**Build beats the data must serve:**
- SCREEN — ingest live tracks/telemetry full-auto
- CORRELATE — fuse AIS + ADS-B + radar into one living picture
- DETECT — cold-start Pattern-of-Life anomaly (NO large historical DB; novel OPAREAs)
- PREDICT — object-level trajectory forecast (NV061)
- SWAN-side — ship machinery / HM&E condition telemetry (the most-reachable v1 feed)
- PROVE — every call sealed in the tamper-evident record (data is the input, not the moat)

**SBIR anchors:** NV063 (anomalous-behavior detection, congested maritime, AIS+ADS-B+radar, explainable AI, no historical DB) · NV061 (predictive movement for object-oriented tracking).

**Hard rails:** open-source / open-access ONLY · LICENSE-FIRST (flag commercial-use suitability — we ship a product + SBIR) · verify every URL, never fabricate a dataset (HONESTY-FIRST) · note registration gates · representative/synthetic stated.

---

## Iteration 1 (Jun 17) — discovery fleet
**Goal:** enumerate + license-flag + URL-verify candidate datasets across 6 categories; rank for THESEUS fit.
**Status:** in flight.
**Fleet (parallel worker subagents → reports in this dir):**
| Cat | Report | Scope |
|---|---|---|
| A | `A_AIS_MARITIME_REPORT.md` | AIS vessel trajectory + Pattern-of-Life + maritime anomaly benchmarks |
| B | `B_AIR_ADSB_REPORT.md` | ADS-B aircraft tracks + AIS↔ADS-B fusion |
| C | `C_RADAR_EOIR_SAR_REPORT.md` | Marine radar / sea-clutter + EO-IR + SAR ship detection + maritime MOT |
| D | `D_SHIP_MACHINERY_CBM_REPORT.md` | SWAN-side HM&E / condition-based maintenance / predictive-maintenance telemetry |
| E | `E_TRAJECTORY_PREDICTION_REPORT.md` | Vessel/maritime trajectory forecasting (NV061) |
| F | `F_SIM_SYNTH_STANDARDS_REPORT.md` | Simulators + synthetic generators + gov open-data portals + standards corpora |

**Deliverable:** `DATASETS.md` — master catalog, ranked, license-flagged, mapped to build beats + NV topics. **SHIPPED.**

**Status:** COMPLETE.
**Deliverables shipped:**
- `DATASETS.md` — master catalog: §1 BLUF · §2 license tiers (commercial-clean / licensed-or-verify / research-only / gated) · §3 by build beat · §4 Warhacker demo data plan · §5 honest gaps + mitigations · §6 action checklist · §7 report index
- 6 category reports (`A_…`–`F_…_REPORT.md`), all URL-verified, license-first, HONESTY-FIRST.

**Headline findings:**
- **Commercial-clean spine exists** end-to-end (MarineCadastre + Ushant AIS · UCI CBM Naval + MetroPT-3 + C-MAPSS machinery · TrAISformer ct_dma trajectory · MIT/Apache tool layer: MSS, Stone Soup, pyais, OpenDDS, SDR capture).
- **Cold-start = own-capture:** RTL-SDR + Pi (AIS-catcher + dump1090-fa) → real airgapped AIS+ADS-B picture. The Warhacker money shot.
- **3 honest gaps:** (a) no open AIS+ADS-B+radar fusion GT → synthesize (Stone Soup) + self-fuse; (b) no open in-situ naval HM&E telemetry → sim-naval + real-adjacent transfer; (c) no open *naval* TP benchmark → commercial AIS-TP + simulated naval maneuvers.
- **⚠️ License conflict:** Piraeus AIS read as CC BY 4.0 (Cat A) vs CC BY-NC-SA (Cat E) — treated NON-COMMERCIAL until the Zenodo field is confirmed.

**Verify-before-SBIR list:** Piraeus license · Brest/Ray-2019 CC tag · DMA reuse string · xView3 T&C · OpenSky §6 joint-IP clause.

**Disposition:** Catalog is the working source of truth for the build team + the NV063/NV061 proposals.

---

## Iteration 2 (Jun 17) — download Tier-1 sets into the repo
**Goal:** pull the commercial-clean / public-domain datasets onto disk, in-repo, without committing bytes to git or touching NC/gated sets.
**Status:** COMPLETE.
**Deliverables shipped:**
- **~2.2 GB downloaded** to `data/datasets/` (gitignored; NOT committed — per CONTRIBUTING.md + license-redistribution discipline). 6 sets:
  - UCI #316 CBM Naval Propulsion (CC BY 4.0) · UCI #791 MetroPT-3 (CC BY 4.0) · NASA C-MAPSS (US-Gov) · Ushant TSS AIS (CC BY 4.0) · TrAISformer `ct_dma` (CeCILL-C) · MarineCadastre US AIS 2024-01-01 (public domain, 7.3M rows).
- `DOWNLOADS.md` — tracked manifest: per-dataset license, source URL, sha256/commit, extracted contents, reproduce script, and the deliberately-skipped (NC/gated) list.
**Discipline held:** only Tier-1 commercial-clean/public-domain pulled; NC + license-unstated + gated sets deliberately skipped; all bytes gitignored (verified `git status` shows nothing under `data/`); checksums recorded; mac cruft removed.
**Notes:** C-MAPSS NASA direct URL now serves HTML (repo moved) → used `edwardzjl/CMAPSSData` mirror. Unrelated pre-existing staged file `demo/data/staged.csv` observed (not THESEUS's; left untouched).
**Next candidate iterations (not started):** (1) wire a maritime ingest adapter that replays MarineCadastre/Ushant AIS through the correlation engine; (2) stand up the SDR own-capture rig (AIS-catcher + dump1090-fa on a Pi); (3) resolve the 5 verify-before-SBIR license items; (4) optional adds (Mendeley GPS-spoofing, TartanAviation, more MarineCadastre days).
