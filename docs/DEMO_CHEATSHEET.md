# THESEUS — PRESENTER CHEAT SHEET
*One page. Glance and go.*

---

## BRING-UP (run both, in order)

```bash
# 1. Strike group + MLflow + all 21 containers + API on :8501
bash deploy/strike_group_up.sh

# 2. Pre-populate the tamper-evident record + preflight GO check
bash deploy/demo_up.sh

# 3. UI
cd frontend/ui && npm run dev
# → http://localhost:5173 → select STRIKE GROUP
```

Operations scene (machinery · contacts · record spine) is live after `demo_up.sh`.
Strike Group scene (3 hulls · AIS map · provenance gate) is live after `strike_group_up.sh`.

---

## THE 6 BEATS (one line each)

| # | Beat | One-liner |
|---|------|-----------|
| 1 | All-systems picture | "Three hulls, 21 live containers, 8 subsystems each — one picture, one watch officer in command." |
| 2 | Anomaly pops | "Cold-start: no historical DB. That contact just jumped faster than physics allows — flagged in plain English, reason and σ shown." |
| 3 | Human decides & seals | "Nothing is automatic — officer accepts, decision seals into the tamper-evident record, leaf count ticks, chain still PASS." |
| 4 | Cut the cord (DDIL) | "Link gone — every container holds last-good, keeps scoring. Ship doesn't go blind." |
| 5 | Ship syncs signed delta | "Link restored — signed, eval-gated delta only; merged model must pass hold-out eval before it promotes." |
| 6 | Provenance gate rejects poisoned delta | "Captured node sends a delta — no attestation chain, rejected at the gate. Fleet stays clean." |

---

## KEY NUMBERS TO SAY

| Number | What it is |
|--------|-----------|
| **3 hulls** | DDG-118 USS Theseus · DDG-119 USS Daedalus · DDG-120 USS Ariadne |
| **21 live containers** | 18 subsystem + 2 UUV Pi-emulation nodes + 1 AE own-systems |
| **8/8 flagship** | DDG-118 runs all 8 subsystems live (others run 6 + can see the full table) |
| **9 @ production** | 9 models registered `@production` in MLflow on :5050 |
| **50 AIS contacts** | Real MarineCadastre tracks; 4 flagged (spoof / jump / loiter / dark-gap) |
| **54-leaf record** | Tamper-evident, Ed25519-signed, in-toto/DSSE attested — `CHAIN VERIFIED · PASS` |

**AUC table (say the headlines, skip auxiliary):**

| Subsystem | AUC |
|-----------|-----|
| SONAR | 1.00 |
| MACHINERY | 1.00 |
| PROPULSION | 0.99 |
| NAV | 0.98 |
| C2 | 0.97 |
| UUV own-systems | 0.94 |
| OWN SYSTEMS (Conv1d AE) | 0.77 |
| AUXILIARY | 0.68 ← say this honestly (proxy dataset) |

---

## HONESTY ONE-LINERS

**Live vs. sealed:**
> "Per-subsystem anomaly scores update live from containers. The hull-level LOCAL MODEL / SIGNED Δ stats are the last sealed fleet-merge — that's intentional, fleet learning syncs on reconnect, not per-second."

**AIS framing A (real tracks):**
> "50 real AIS contacts from MarineCadastre — Gulf of Mexico + Ushant cross-validation. Not simulated."

**AIS framing B (own-systems):**
> "The contacts layer is the tactical picture. The machinery / propulsion / sonar layers are the own-systems health picture. Two separate threat models on the same dashboard."

**cATO framing:**
> "We emit OSCAL assessment-results and in-toto/DSSE attestations so an Authorizing Official can accredit the learning pipeline, not frozen weights. No AO has signed this record yet — the mechanism is what's novel, and it's demonstrable right now."

---

## IF IT BREAKS

| Symptom | Recovery |
|---------|----------|
| **Screen shows SIM FEED** | Cut to 60s recording — keep narrating; beats are identical |
| **A container is down** | Leave it — system degrades gracefully; mention it: "edge containers are isolated, a single failure doesn't cascade" |
| **MLflow down** | Containers hold last-good and keep scoring — **this is the DDIL beat, lean into it**: "that's exactly what happens under denied comms" |
| **Operations scene is dark** | `bash deploy/demo_up.sh` in a second terminal — 30 seconds, record repopulates |
| **Strike Group scene is missing hulls** | `bash deploy/strike_group_up.sh` then give it 20s for all containers to start |
| **API :8501 not responding** | `python3 demo/api.py --port 8501` from repo root |
| **UI won't load :5173** | `cd frontend/ui && npm run dev` — check Node version ≥ 20 |
