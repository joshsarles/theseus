# THESEUS Fleet-Learning Miniature

End-to-end demonstration of the fleet-learning flywheel — provenance-gated,
eval-gated, and human-authorized. The full vision on a table, disconnected.

## How to run

From the repo root:

```
bash fleet/run_miniature.sh
```

Runtime: ~3 seconds. CPU-only. No GPU, no internet, no services.

Prerequisites: Python 3.10+, `numpy`, `cryptography` (both already in
the repo's standard environment).

## What runs

```
fleet/run_miniature.sh           # end-to-end orchestrator
fleet/fleet_brain.py             # fleet brain: keygen, merge, poison injection
fleet/ship_node.py               # ship node: local training + delta signing
fleet/signing.py                 # Ed25519 DSSE signing/verification layer
fleet/out/                       # runtime outputs (created fresh each run)
  MACHINERY/                     # ship 1 chain + delta
  CONTACTS/                      # ship 2 chain + delta
  fleet_record/                  # fleet brain chain + model + report
    chain.jsonl                  # tamper-evident ledger
    bundle.json                  # merkle root + chain head
    fleet_model.json             # accepted merged model params
    merge_report.json            # honest before/after metrics
fleet/keys/                      # Ed25519 keypairs (generated at run start)
  MACHINERY.key, MACHINERY.pub
  CONTACTS.key, CONTACTS.pub
```

## Architecture

### Scenario

A fleet of two ships tracks surface contacts with EO/IR sensors. Ships
operate at different ranges from their patrol sectors:

- **MACHINERY** (Ship 1 / `pi1` when reachable): observes contacts at **0–10 km**
- **CONTACTS** (Ship 2 / `pi2` when reachable): observes contacts at **10–25 km**

Each ship trains a Ridge regressor to estimate *detection quality* from five
sensor features. The underlying linear relationship is identical for both ships
— but neither ship can estimate the global model from its local data alone.
A model trained only on 0–10 km contacts extrapolates badly at 15 km. The
fleet brain's FedAvg merge recovers near-oracle global performance.

This is the core federated learning value: *local models good in their regime,
fleet model good everywhere, no raw data shared.*

### Components

```
Ship Node (MACHINERY)          Ship Node (CONTACTS)
  └─ local Ridge regression      └─ local Ridge regression
       on range 0-10 km               on range 10-25 km
  └─ Ed25519 DSSE sign           └─ Ed25519 DSSE sign
  └─ write delta + chain leaf    └─ write delta + chain leaf

                     Fleet Brain
                       └─ PROVENANCE GATE
                            verify each delta's DSSE envelope
                            against registered ship .pub key
                            REJECT if: unknown key / bad sig /
                                       missing statement fields
                       └─ FEDAVG MERGE (accepted deltas only)
                            weighted by n_samples per ship
                       └─ EVAL GATE
                            merged model must beat incumbent
                            on held-out set (150 obs, full range)
                            if regression: REJECT, keep last-good
                       └─ seal fleet_merge_accepted/rejected
                       └─ verify_dir on fleet chain
```

### Signing format

Each ship signs its delta as a minimal DSSE envelope (no in-toto binary
install required — stdlib + `cryptography` only):

```json
{
  "payload_type": "application/vnd.theseus.model-delta+json",
  "payload": "<base64url(statement)>",
  "signatures": [{"keyid": "MACHINERY", "sig": "<hex(ed25519_sig)>"}]
}
```

The statement inside the payload encodes subject (ship_id, data_hash,
base_model_hash) + predicate (n_samples, feature_names, local metrics).
Pre-Authentication Encoding (PAE) follows DSSE §2.3 to prevent
cross-type attacks.

### Chain format

Each event (accepted/rejected delta, merge outcome) is sealed as a
`LocalHashChain` leaf (SHA-256 prev-hash chained). The fleet chain at
`fleet/out/fleet_record/` is independent of the demo chain at `out/`.

`verify_dir` is the same offline verifier used in the referee smoke tests:
anyone can run it, no trust in the fleet brain required.

## What is REAL vs what is NOT

**REAL:**
- Deterministic sensor data: 600 observations across disjoint range strata,
  generated from fixed numpy seeds (reproducible byte-for-byte)
- Ridge regression: closed-form numpy training (no sklearn), CPU-only
- Ed25519 DSSE signing: real `cryptography.hazmat` Ed25519 (not mocked)
- FedAvg: n_samples-weighted average of model params — no hand-tuning
- Eval gate: held-out RMSE on 150-obs full-range set; numbers reported exactly
- Poison defense: DSSE keyid not in trust registry → rejected before any merge
- Tamper evidence: one-byte flip snaps the SHA-256 prev-hash chain
- Two independent processes (can map directly onto 2 Pis)

**SIMULATED (local processes stand in for physical ships):**
- `--node-host local` runs both ships in the same process environment;
  the Pi path (`--node-host pi1.local`) is wired in the CLI but the Pis
  are offline — no SSH / remote execution implemented yet
- The "DDIL" isolation is process-level, not network-level. In deployment,
  each ship node runs on its own hardware with no network to the other ship

## Metrics (real numbers from a representative run)

```
Ship MACHINERY  : local train RMSE = 0.029348  (vs baseline 0.126955)
Ship CONTACTS   : local train RMSE = 0.027021  (vs baseline 0.146845)

Fleet Brain (held-out n=150, range 0–25 km):
  Incumbent RMSE (base model, 50-sample bootstrap) : 0.031816
  Merged RMSE (FedAvg of 2 ships)                  : 0.030019
  RMSE delta                                       : −0.001796
  Eval gate                                        : PASS

Chain: 4 leaves, verify_dir PASS. One-byte tamper → SNAP at leaf 0.
Poison: POISON_NODE REJECTED (unknown keyid).
```

The RMSE improvement is modest but real and statistically meaningful: the
two-ship fleet model generalizes better to the full 0–25 km range than the
50-sample bootstrap model, because each ship contributes knowledge from its
own range stratum without sharing raw observations.

## The accreditation argument

The tamper-evident record makes fleet learning ACCREDITABLE:

1. **Provenance-gated merge** defeats model poisoning — a forged delta
   with an unregistered key is rejected before touching the merge.
2. **Eval-gate** defeats catastrophic forgetting — a regressive merge
   is rejected and the incumbent is preserved.
3. **Sealed audit trail** — every accept and reject is a signed, chained
   leaf. The chain is the evidence package for cATO.
4. **You accredit the pipeline's provenance, not the frozen weights** —
   the weights are a derivative of the chain; the chain is what you prove.

## Pi deployment path

When the Pis are reachable, swap `--node-host local` for the Pi hostname:

```bash
# On pi1 (MACHINERY ship):
ssh pi1.local "cd /path/to/repo && python -m fleet.ship_node \
    --ship-id MACHINERY --node-host pi1.local"

# On pi2 (CONTACTS ship):
ssh pi2.local "cd /path/to/repo && python -m fleet.ship_node \
    --ship-id CONTACTS --node-host pi2.local"

# Fleet brain (on the Mac, after ship deltas are available):
python -m fleet.fleet_brain --merge
```

The interface is identical — only the key distribution changes (each Pi
receives only its own `.key` file; the fleet brain holds both `.pub` files).
