# THESEUS — Live Demo Script
*The 3-minute judge-facing story. Every beat is real and provable — nothing mocked. Owner: WARHACKER. Rehearse with the team day-2; record a 60s fallback.*

## The one-sentence pitch
**Theseus is the onboard decision-support platform that keeps a warship's AI learning under denied comms — every model update and every human decision sealed in a tamper-evident record, deployable to a hull on Defense Unicorns' accredited airgap rails.**

## Setup (before judges arrive)
- **Screen:** the CIC dashboard — `http://localhost:5173` (full-screen). Live API on `:8501`.
- **Pre-staged offline:** the demo loop, real UCI #316 + MarineCadastre AIS, the UDS package + images (no internet needed — that's the point).
- **Optional second screen:** a terminal for the DDIL beat + the `uds`/`kubectl` evidence.
- **Hardware:** Tier-1 = this Mac (+ Ryzen/Blackwell stand-in); Tier-2 = the 2 Pis on Tailscale (William).

---

## The 3 minutes (beat by beat)

### 0:00 — "One ship, all systems." *(the picture)*
**Say:** *"This is Theseus — the ship's brain. One screen, every system: machinery, contacts, power, navigation, damage control. It's decision-support — the watch officer is always in command."*
**Do:** the CIC is up. Point at the **left systems column** (honest: machinery + contacts live, the rest instrumented/standby), the **tactical picture** (real AIS contacts), and the **record spine** on the right — **CHAIN VERIFIED · PASS**.
**Proof:** real RMSE `0.0038` on the machinery model; real AIS tracks; the record is a live hash chain.

### 0:30 — "It sees what shouldn't be there." *(the anomaly — NV063)*
**Say:** *"Theseus runs a cold-start Pattern-of-Life cell — no historical database. It just flagged this contact: AIS positions jumping faster than physics allows — a likely spoof. And it explains why, in plain language, for the watch."*
**Do:** click the **POSITION JUMP** alert → show the **why** + **recommended action**.
**Proof:** `demo/ais_pol.py` on real MarineCadastre data; the explanation is a local LLM (runs on the Pi-class model, airgapped).

### 1:00 — "The human decides — and it's provable." *(human-in-command, the climax)*
**Say:** *"Nothing is automatic. The officer accepts or overrides — and that decision is sealed into the tamper-evident record, forever."*
**Do:** click **ACCEPT** (or OVERRIDE) → watch a new **HUMAN DECISION** leaf seal into the spine, leaf count ticks up, **CHAIN VERIFIED · PASS**.
**Proof:** `POST /api/decision` seals a real leaf; `verify_dir` re-verifies the whole chain live.

### 1:30 — "Now cut the comms." *(DDIL — the differentiator)*
**Say:** *"At sea you lose the link. Watch."* *(pull the cord / disable the network.)* *"The ship keeps serving its last-good model. A shore update arrives in a signed bundle — Theseus promotes it, seals it, and if it's bad, rolls back — all offline. The record holds the line."*
**Do:** run `deploy/ddil_beat.sh` (or the multi-Pi failover over Tailscale — William): cord-pull → last-good serves → update promotes + seals → bad-update → rollback → tamper → record SNAPs.
**Proof:** the script prints PASS at each step; the record verifies with no shore connection.

### 2:15 — "And it ships to a real hull." *(Defense Unicorns / death-proof)*
**Say:** *"This isn't a slideware prototype. It deploys on Defense Unicorns UDS — the same accredited airgap rails the Navy uses. Our policies are machine-enforced: no egress, append-only record, human-in-command required before any action is admitted. Signed bundle, full SBOM."*
**Do:** show `kubectl get pods` (Theseus on uds-core), the **Pepr admission denying a violating pod**, and the **Zarf SBOM + cosign** signature. *(Evidence: `deploy/UDS_DEPLOY_EVIDENCE.md`.)*
**Proof:** real `uds deploy`; real admission denial; real SBOM artifact.

### 2:45 — "Why it matters." *(the close)*
**Say:** *"Theseus is the edge model-delivery spine for the fleet — keep ships' AI current and accountable under DDIL, inherit ATO instead of rebuilding it, with a record that doubles as accreditation evidence. Decision-support, human-in-command, real on real. That's the ship that keeps learning at sea."*

---

## Who buys this (have the answer ready)
- **Near-term:** NAVSEA SBIR **NV063** (anomaly/Pattern-of-Life, explainable, cold-start) — opens 6/24; this demo *is* the prototype. Companion: **NV061** (trajectory).
- **The gate (be honest):** a **program-office sponsor + ATO** is the real long pole — UDS control-inheritance shortens it, but it's still the work. *(Joshua: land an attributed AO/PEO sentence.)*

## Fallback
- If live fails: a **60s screen recording** of the five beats (Aaron to capture day-2). The dashboard + `ddil_beat.sh` are the most reliable beats; lead with those.

## Pre-flight checklist (run before the demo)
- [ ] `frontend/ui` up on :5173; `demo/api.py` on :8501 (record populated: machinery + contacts).
- [ ] `python3 -m pytest tests/ -q` → green.
- [ ] `bash deploy/ddil_beat.sh` → all PASS.
- [ ] UDS deploy reachable (or the recorded evidence ready).
- [ ] 60s fallback recording on the demo machine.
- [ ] Internet OFF for the airgap beats (prove it runs disconnected).
