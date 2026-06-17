# THESEUS

**The self-controlled ship brain — onboard analytics + edge model-management under DDIL.**

When a warship loses its link to shore (DDIL: denied, degraded, intermittent, limited), its systems data is on its own — scattered across stovepiped systems, watched by a handful of sailors. Theseus deploys, manages, and runs AI models **at the edge** on a resource-limited shipboard-analog cluster: it fuses available (SWAN-side) systems data into one live picture, flags what's failing or off-normal, and drafts the call for a human to approve — running fully disconnected, from one signed bundle, with **every model update and decision sealed in a tamper-evident, offline-verifiable record.** Human always commands. Integrate, never replace.

> *Like the Ship of Theseus — every plank can be replaced and she's still herself, because the brain that runs her is one.*

Built at Warhacker (Jun 16–19 2026) by a team of NAVSEA + NIWC engineers (Force AI). AGPL-3.0.

## What it does (team objectives)
1. **Deploy** AI models at the edge (shipboard-like, resource-limited).
2. **Centrally manage** models at the edge (MLflow registry / tracking / monitoring).
3. **Live-update** models from the edge.
4. **Stage** model updates from shore **without sneakernetting** (UDS/Zarf airgap bundle).

## Stack
**Python 3.14.4** · PyTorch (train) → ONNX (edge) · **MLflow 3.13** (central server) · **Podman** (rootless OCI) · Raspberry Pi cluster (AI HAT+2) · **UDS/Zarf** (airgap deploy) · tamper-evident hash-chained record · Force OS (orchestration option).

## Where to look first
- **`docs/INDEX.md`** — the map of everything.
- **`docs/vision/TEAM_OBJECTIVES_AND_LOG.md`** — objectives + stack + living log (updated as Slack evolves).
- **`KANBAN.md`** — the board.
- **`docs/setup/MLFLOW_PODMAN.md`** — run MLflow on Podman (with offline/airgap staging).
- **`docs/research/`** — SBIR demand (NV063), datasets (UCI #316, OMTAD), the design council.
- **`docs/integration/DEFENSE_UNICORNS.md`** — Theseus-on-UDS (inherit the ATO + the hull on-ramp).

## The spine in this repo (the trust/record layer — transfers directly to Theseus)
The code here is the **tamper-evident record + advisory-only (human-in-command) gate + UDS/Zarf packaging** — i.e. Theseus's *moat* layer. It currently observes vendor-AI decisions; for Theseus it reframes to **ship-systems telemetry** (same engine, new observation source). Every model promotion/rollback and every alert/decision gets sealed here.

```bash
make smoke    # ingest -> advisory-only policy gate -> hash chain -> proof bundle
make verify   # offline verification of the record -> PASS
make tamper   # flip one byte -> chain SNAPS (tamper-evident)
make demo     # narrated end-to-end run
```
- `referee/chain.py` — SHA-256 hash-chained tamper-evident record + offline verifier (→ seals model versions + decisions).
- `referee/policy.py` — fail-closed, **advisory-only** gate (→ the human-in-command recommend→approve loop).
- `referee/intake.py` — observation ingest (→ ship-systems `Observation` schema; see `docs/research/council/COUNCIL_BRIEFS.md`).
- `zarf/` + `lula/` — UDS packaging + compliance-as-code skeletons (→ the airgap bundle / ATO evidence).

## Rails (carry into every demo and slide)
SWAN-side data only (combat systems are air-gapped/classified) · decision-support, human-in-command — never autonomous ship control · tamper-**evident**, not tamper-proof · integrate-not-replace · real/representative data, stated as such.

## New teammate
Run the Quickstart, read `docs/INDEX.md` and `docs/vision/TEAM_OBJECTIVES_AND_LOG.md`, grab a card off `KANBAN.md`, and read `CONTRIBUTING.md` before your first commit (the IP guard is real and enforced).
