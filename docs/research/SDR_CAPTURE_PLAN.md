# THESEUS — SDR Capture Plan (own real AIS + ADS-B, airgapped)
*Build-ready rig for William (NAVSEA). A ~$30–100 RTL-SDR + Raspberry Pi that has THESEUS generate its **own live maritime + air picture** on representative hardware — no internet, no historical DB. Source facts: `docs/research/datasets/F_SIM_SYNTH_STANDARDS_REPORT.md`. Feeds the loop's Data contract: `demo/README.md`.*

## 1. Why this is the demo centerpiece
Cold-start, fully airgapped, **real** data. A cheap dongle on a Pi proves NV063's hardest requirement (learn "normal" in-situ, no large historical DB) and the DDIL story (no cloud feed reaches a ship at sea). The picture THESEUS reasons over is one it captured itself, on the edge node, with the network cable unplugged.

## 2. Hardware shopping list (2026 prices)
**Frequency reality:** AIS lives at **161.975 / 162.025 MHz** (VHF marine), ADS-B at **1090 MHz** — ~900 MHz apart. One RTL-SDR has only ~2.4 MHz instantaneous bandwidth, so **one dongle cannot do both at once.** AIS-only = one dongle (the maritime money shot). AIS **+** ADS-B cross-correlation = **two dongles**.

| Item | Minimum (~$60, AIS only) | Good (~$160, AIS + ADS-B) |
|---|---|---|
| SDR dongle | 1× RTL-SDR Blog V4 kit w/ dipole — **$40** | 2× RTL-SDR Blog V4 — **$80** |
| Antenna | dipole from kit (tune ~162 MHz) | + 1090 MHz ADS-B antenna — **$25** |
| Compute | Raspberry Pi 4 (2 GB) — **$45** *(reuse if on hand → ~$0)* | Raspberry Pi 5 (4 GB) — **$60** |
| Storage | 32 GB microSD — **$10** | 64 GB microSD — **$12** |
| Optional | — | 1090 MHz LNA/filter (e.g. FlightAware) — **$20** |

Notes: V4 has a built-in bias-tee to power an LNA; Nooelec NESDR SMArt (~$35) is a fine substitute. If using two dongles, set unique serials so they don't collide: `rtl_eeprom -d 0 -s 00000001` (AIS), `… -s 00000002` (ADS-B).

## 3. Setup (copy-pasteable, Raspberry Pi OS)
**AIS receiver — AIS-catcher (GPL, sidecar process):**
```bash
sudo apt update && sudo apt install -y curl
# one-line install (prebuilt package, statically links Osmocom for RTL-SDR V4):
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/jvde-github/AIS-catcher/main/scripts/aiscatcher-install) -p"
AIS-catcher -L                              # confirm dongle + build features
# live dual-channel decode, auto gain, web map on :8100, NMEA out to UDP :10110
AIS-catcher -A -g auto -v -N 8100 -u 127.0.0.1 10110
```
Expected: streaming `!AIVDM,1,1,,B,15Muq...` lines + decoded ship rows; live plots at `http://<pi>:8100`. (Optional Visual Web Control on `:8110`.)

**ADS-B receiver — dump1090-fa (GPL, sidecar process):**
```bash
# add FlightAware piaware apt repo, then:
sudo apt install -y dump1090-fa
```
Expected: SkyAware air map at `http://<pi>:8080`; live aircraft JSON at `http://<pi>:8080/data/aircraft.json` (also `/run/dump1090-fa/aircraft.json`). 1090 MHz, no extra flags for basic capture.

## 4. How it feeds THESEUS
```
AIS-catcher  ──NMEA/JSON (UDP :10110)──▶  pyais decode  ──▶  normalize to MarineCadastre schema
                                                                (MMSI, BaseDateTime, LAT, LON,
                                                                 SOG, COG, Heading, VesselName,
                                                                 VesselType, Status)
                                                                      │
                                                                      ▼
                                                   demo/ais_pol.py  (Pattern-of-Life: loiter /
                                                   AIS-dark-gap / position-jump / overspeed)
                                                   + Data contract (demo/data/*.csv shape)

dump1090-fa  ──aircraft.json──▶  air picture  ──▶  AIS↔ADS-B cross-correlation (track de-confliction)
```
AIS-catcher can emit JSON directly, so `pyais` (MIT) is only needed when consuming raw NMEA. Keep the column shape identical to MarineCadastre AIS so `ais_pol.py` and the loop's Data contract ingest the live capture exactly as they do the historical bulk set — swap the source, not the schema.

## 5. Legal + rails
- **RX-only is legal.** Per USCG NAVCEN, only *transmitting* AIS base stations are restricted (47 CFR); receiving/decoding AIS and ADS-B is unrestricted. We never transmit.
- **GPL sidecar discipline.** AIS-catcher, rtl-ais, dump1090-fa are **standalone binaries** consumed over a socket/JSON — **never statically linked** into THESEUS's proprietary core. No copyleft infection.
- **Synthetic-vs-real is labeled** at ingest; live SDR rows carry a real-source tag distinct from any simulator augmentation.
- **Human-in-command.** THESEUS recommends; the watch officer accepts/overrides; nothing is actioned automatically (`demo/show.py` surface).

## 6. Airgap / DDIL framing
This rig runs with **zero network** — antenna → dongle → Pi → THESEUS, cable unplugged. That is precisely the point: cloud AIS feeds (aisstream, GFW, Copernicus) **cannot reach a ship at sea**, so they only seed the cold-start model ashore at build time. Underway, **own SDR capture is the only runtime-legal data path** — and this $60–160 rig demonstrates it physically at the venue.
