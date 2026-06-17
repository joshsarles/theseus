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

**Deliverable:** `THESEUS_DATASETS.md` — master catalog, ranked, license-flagged, mapped to build beats + NV topics.

**Disposition:** TBD on fleet return.
