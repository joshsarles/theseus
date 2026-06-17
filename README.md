# THE REFEREE
### Independent AI assurance & accountability for the multi-vendor mission

> **REPO STATUS: LOCAL-ONLY.** Do not push or share until the legal IP-scope check clears (see CONTRIBUTING.md). Intended event license: AGPL-3.0.

When an autonomous system loses its link, its AI is on its own. The Referee answers the question nobody can answer today: **is the AI still operating inside its authorized parameters — and can you prove what it did afterward, with a record nobody can quietly edit?**

The Referee **observes** decisions emitted by any vendor's AI (it never runs the mission), gates each one against an explicit authorized-parameters policy, and writes every observation into a **hash-chained, tamper-evident, replayable record** that anyone can verify offline. Advisory-only by construction: the human and the accreditation process remain the authority of record.

## Quickstart (zero dependencies, Python 3.10+)

```bash
make fixtures   # generate the deterministic 25-observation smoke fixture
make smoke      # ingest -> policy gate -> hash chain -> proof bundle (asserts expected outcomes)
make verify     # offline verification of the record  -> PASS (green)
make tamper     # flip one byte in leaf 9, re-verify  -> chain SNAPS at leaf 9 (red)
make demo       # narrated end-to-end run
make guardian   # GUARDIAN narrative demo: the Cannonico case, told for a command audience
```

If `make smoke` is green, you have the full Beat 1-3 spine running locally.

### `make guardian` — the command-audience story (Defense Unicorns)
A narration layer on top of the same engine (it does NOT reimplement the gate or the
chain). It plays a scripted, synthetic, unclassified scenario — an autonomous drone
that loses contact and drifts out of its authorized parameters — and reads the engine's
verdict out loud, line by line: **catch the AI going out of bounds → keep a human in
command → keep an unbreakable record** (verify, tamper one byte, GUARDIAN catches it,
restore and re-verify). Advisory-only: the human always decides; GUARDIAN never takes
the action.
- `referee/guardian_demo.py` — the runner (`--plain` for runbook capture, no colors).
- `fixtures/scenario_cannonico.py` — the ~11-step story, lowered into the engine's native observation shape.
- `tests/test_scenario_cannonico.py` — fidelity checks (the engine's verdict must match the narration on every step) + the proof beat.

## Architecture (60 seconds)

```
vendor AIs ──CoT/JSONL──> intake ──> [hash-chain leaf written FIRST]
                                    └─> policy gate (fail-closed, advisory-only)
                                          ├─ BREACH/WARN -> violation (also chained)
                                          └─> scorecard / drift jobs (event: production wheels)
session ──> proof bundle (Merkle root [+ RFC-3161 at event]) ──> offline VERIFY
```

- `referee/schemas.py` — `VendorDecisionObservation`, `AuthorizedParameterPolicy`, `PolicyViolation`
- `referee/intake.py` — JSONL (+ CoT at event) ingest; **chain-append happens at ingest, before any judgment**; malformed input is chained too (observability includes garbage)
- `referee/policy.py` — the authorized-parameters gate: geofence, confidence floor, latency SLA, classification ceiling, DDIL allowlist, forbidden classes/decision-types, provenance-required. Unevaluable rule ⇒ BREACH (fail-closed).
- `referee/chain.py` — reference tamper-evident chain (SHA-256 prev-hash + Merkle root) + offline verifier. At the event this seam swaps to the production signed ledger (retained IP, brought as wheels/containers).
- `referee/demo.py` — scenario driver + CLI.
- `referee/aiir.py` — AIIR v0.1 incident-record emitter: every smoke/demo run writes one `out/incident_records/aiir_*.json` side artifact per BREACH (schema-checked against the vendored `referee/aiir_v0_1.schema.json`, stdlib-only; records are never chained — verify/tamper behavior unchanged).
- `cot/` — Cursor-on-Target UDP listener + emitter (typed stubs; Day 1 task).
- `fixtures/` — synthetic only. `zarf/` + `lula/` — UDS packaging + compliance-as-code skeletons.

## Honesty rules (carry into every demo and slide)
Tamper-**evident**, not tamper-proof · advisory-only · recorded-inference replays are labeled as such · no claims about real vendors (vendor-a/b/c are logical) · "court-admissible by construction; not yet litigated" · synthetic/unclassified data only.

## Your first hour (new teammate)
1. Run the Quickstart above. 2. Read `docs/ONBOARDING.md` (one page). 3. Pick up your slot's Day-plan task from the team board. 4. Read CONTRIBUTING.md **before your first commit** (the IP guard is real and enforced).
