<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# THESEUS rail-1 admission tests — human-in-command, record-bound

These fixtures + `verify.mjs` prove that the THESEUS Pepr rail-1
(`deploy/uds/pepr/theseus-policies.ts`) **binds a decision/autonomy action's
approval to a genuinely sealed, chain-verifying `human_decision` leaf** in the
tamper-evident record — closing the "type any string = approved" kill-shot.

## What changed (the kill-shot fix)

**Before:** rail-1 admitted ANY non-empty `human-approved-by` string and only
*warned* on a missing `approval-record-ref`. A pod with `human-approved-by: "x"`
was admitted. (Reproduced live: `kubectl apply --dry-run=server -f
bad-legacy-ref.yaml` against the pre-fix webhook printed `pod/... created`.)

**After:** a decision action (label `theseus.forceos.ai/action`) is DENIED unless
all of:

| Check | What it requires | Enforced |
|-------|------------------|----------|
| **A1** | a non-empty `theseus.forceos.ai/human-approved-by` | always (structural) |
| **A2** | `theseus.forceos.ai/approval-record-ref` is **canonical** — `theseus-record://<kind>/<obs_id>@sha256:<64hex>` — pinning a leaf_hash | always (structural) |
| **A3** | a `theseus-approval-verify` init-container wired to the **same** ref (`THESEUS_APPROVAL_REF`) + a read-only record mount (the runtime gate, Layer C) | always (structural) |
| **B**  | if the record is mounted to the controller (`THESEUS_RECORD_DIR`), the ref is **chain-verified against the real record at admission** — forged hash / absent leaf / SNAP → DENIED | when record mounted (the live flex) |

A1–A3 are the **structural binding**: they are enforced at admission with no
record mount, so a non-empty string alone can never pass and there is nothing to
type that names a sealed leaf unless one was actually sealed. Layer B is the
**chain-verify flex**: mount the record into the Pepr controller and a forged ref
is rejected at admission, before the pod is ever scheduled. Layer C (the
init-container running `referee/verify_record.py`) is the in-cluster re-check that
holds even when the controller has no record mount.

**Honest scope:** without a controller record mount, admission enforces the
structural binding (A1–A3) and *defers the cryptographic chain-verify to the
in-cluster verify gate (Layer C)*; the approve-path warning says so verbatim. With
the mount (Layer B), the chain-verify also happens at admission. Today's
`referee/verify_record.py` CLI verifies the whole mounted record (`--record`); the
ref it is bound to travels in `THESEUS_APPROVAL_REF`, and the leaf-specific resolve
is enforced at admission (Layer B) and structurally (A2/A3).

## Fixtures

| Fixture | Expected | Why |
|---------|----------|-----|
| `good-approved.yaml`  | **ADMITTED** | approver + canonical ref to a real sealed `human_decision/accepted:CTC-7` leaf + wired verify gate; Layer B chain-verifies it |
| `good-compliant.yaml` | **ADMITTED** | a plain part-of pod that satisfies rails 2 + 3 (no decision action) |
| `bad-noapproval.yaml` | **DENIED (A1)** | action declared, no approver |
| `bad-legacy-ref.yaml` | **DENIED (A2)** | the literal pre-fix kill-shot: `human-approved-by: "x"` + legacy path ref `out/record/chain.jsonl#leaf2` (not canonical) |
| `bad-nogate.yaml`     | **DENIED (A3)** | perfect canonical ref to the real leaf, but NO verify init-container |
| `bad-forged-ref.yaml` | **DENIED (B)**  | canonical ref + gate, but the pinned leaf_hash is forged (all-f); Layer B catches the hash mismatch |
| `bad-absent-ref.yaml` | **DENIED (B)**  | canonical ref + gate, but names a leaf (`overridden:CTC-999`) never sealed; Layer B finds no such leaf |
| `bad-privileged.yaml` / `bad-root.yaml` / `bad-hostpath.yaml` | **DENIED** | rails 2 + 3 (containment / hardened / hermetic) |

`good-approved.yaml`, `bad-nogate.yaml` carry `__LEAF_HASH__` — the harness seals a
fresh real record and substitutes the actual leaf_hash, so ADMIT is proven against a
genuinely sealed leaf, never a hardcoded string.

## Run it — offline harness (no cluster; the documented dry-run)

```bash
# from deploy/uds/pepr:  npm run verify:rail1
node deploy/uds/admission-tests/verify.mjs
```

The harness (all real, no mocks):
1. seals a genuine record via the **real** `referee/chain.py` (`demo/_record.seal`,
   the exact path `/api/decision` uses) and confirms `verify_dir()` PASSes;
2. compiles the **actual** `theseus-policies.ts` + `record-binding.ts` with esbuild
   and imports the **exact** exported `evaluateRule1()` the webhook runs (no
   re-implementation, no drift);
3. runs every fixture through `evaluateRule1()` with the real record mounted
   (Layer B live) → forged/absent/legacy/no-approver/no-gate DENIED, real-bound
   ADMITTED;
4. re-runs with Layer B off → A1/A2/A3 still DENY; good pod admitted on the
   structural binding with the honest "chain-verify deferred to the in-cluster
   gate" warning;
5. negative control: the same record that ADMITS `good-approved` DENIES
   `bad-forged-ref` → the denial is the **ref**, not a broken record. (A 1-char
   mutation of the good ref hash flips ADMIT→DENY, so the test is not vacuous.)

Exit 0 = all cases behaved as expected.

## Run it — live k3d (real admission webhook)

`pepr build` compiles cleanly (`dist/pepr-module-*.yaml`). To exercise the live
webhook **without touching the running demo cluster** (`k3d-theseus`), deploy the
module to an isolated throwaway cluster (the v1.2.1 controller image is cached
locally, so no GHCR pull):

```bash
cd deploy/uds/pepr && npx pepr build
k3d cluster create theseus-pepr-test --no-lb
k3d image import ghcr.io/defenseunicorns/pepr/controller:v1.2.1 -c theseus-pepr-test
kubectl --context k3d-theseus-pepr-test create namespace theseus
kubectl --context k3d-theseus-pepr-test apply -f dist/pepr-module-*.yaml
# kubectl --context k3d-theseus-pepr-test apply -f ../admission-tests/<fixture>.yaml
k3d cluster delete theseus-pepr-test   # ephemeral; never touches the demo
```

For the **Layer B live flex**, ConfigMap the sealed `chain.jsonl`/`bundle.json`
into `pepr-system`, mount it into the controller at `/var/lib/theseus/record`, and
set `THESEUS_RECORD_DIR` on the controller — then `bad-forged-ref` / `bad-absent-ref`
are DENIED at admission and `good-approved` is ADMITTED with "ref VERIFIED at
admission." (Validated on an isolated cluster; results below.)

### Verified results (isolated k3d, this lane)

Structural (A+C, no record mount):
`bad-noapproval→DENIED(rail1 A1)`, `bad-legacy-ref→DENIED(rail1 A2, "MALFORMED…
must be bound to a sealed decision")`, `bad-nogate→DENIED(rail1 A3)`,
`good-approved→ADMITTED("ref structurally bound")`, plus
`bad-privileged/bad-root/bad-hostpath→DENIED`, `good-compliant→ADMITTED`.

Layer B (record mounted into controller):
`good-approved→ADMITTED("ref VERIFIED at admission … leaf idx=1")`,
`bad-forged-ref→DENIED("sealed hash … does not match the ref's pinned … forged
leaf_hash")`, `bad-absent-ref→DENIED("no sealed leaf … in the record")`.
