# THESEUS rails — Pepr admission policies

Cluster-enforced version of the THESEUS rails. Where `zarf/manifests/job.yaml`
*opts in* to a hardened `securityContext`, this Pepr module makes the rails a
hard admission rule: a Pod that violates a rail is **denied** at create/update.

Decision-support only — never autonomous ship control. tamper-**evident**, not
tamper-proof. SWAN-side/unclassified only. Deployable; ATO is the gate.

## What it enforces (on Pods in the Theseus namespaces)

| Rail | Trigger | Behavior |
|------|---------|----------|
| **1. human-in-command** | Pod has label `theseus.forceos.ai/action` | **Deny** unless annotation `theseus.forceos.ai/human-approved-by` is non-empty. Warns if `theseus.forceos.ai/approval-record-ref` is missing. |
| **2. contained / no-egress** | Pod labeled `app.kubernetes.io/part-of: theseus` | **Deny** `hostNetwork`/`hostPID`/`hostIPC`/`privileged`. Roles `model`/`explainer`/`inference`/`edge-runner` must carry `theseus.forceos.ai/egress: none`. (The actual egress block is Istio default-deny + the UDS Package NetworkPolicy — this stops any pod from *declaring* an escape hatch.) |
| **3. append-only + hardened** | Pod labeled `app.kubernetes.io/part-of: theseus` | **Deny** hostPath volumes; **deny** a writable mount of the record volume (`theseus-record`/`referee-record`/`record`, or paths under `/var/lib/theseus/record`, `/work/out/record`, `/out/record`); require `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop:["ALL"]`. Warns if seccomp ≠ `RuntimeDefault`. |

The label/annotation contract lives at the top of `theseus-policies.ts`. Edit
`NS_THESEUS` to match your deploy namespaces.

## Build (compiles to a deployable webhook)

```bash
cd deploy/uds/pepr
npm install
npx pepr build          # esbuild bundle + ValidatingWebhookConfiguration + Helm chart + dist/zarf.yaml
```

`npx pepr build` emits to `dist/`:
- `pepr-module-<uuid>.yaml` — the `ValidatingWebhookConfiguration` + controller
  Deployment + RBAC (apply with `kubectl apply -f` for a quick test).
- `<uuid>-chart/` — Helm chart.
- `zarf.yaml` — a Zarf package definition (image
  `ghcr.io/defenseunicorns/pepr/controller:v1.2.1`) so the policy travels in the
  **same airgap bundle** as the referee package. For the full UDS story, add this
  to `zarf/uds-bundle.yaml` `packages:` (after uds-core).

This module is **validate-only**, so Pepr generates a `ValidatingWebhookConfiguration`
only (no mutation). `onError: reject` (in `package.json` `pepr` block) = fail-closed.

## Local dev / try it

```bash
npx pepr dev            # runs the webhook locally against your kubecontext (k3d works)
# then: kubectl apply a Pod that violates a rail -> admission denied with the rail message
```

## Honest scope
- Admission-time enforcement. It guarantees no Theseus pod can *declare* an
  egress/host/record escape; it does not by itself sever the network — that's
  Istio default-deny + NetworkPolicy from the UDS Package CR.
- Rule 3 keeps the record volume read-only to the workload (no silent in-place
  rewrite). Tamper *detection* is still `referee/chain.py`'s offline verifier.
- These are controls — evidence toward AC-6 / SC-7 / AU-9 — not an ATO.

## Verified against
`pepr@1.2.1`, `kubernetes-fluent-client@3.11.7`, `@kubernetes/client-node` v1.34
types. `npx tsc --noEmit` (strict) and `npx pepr build` both pass.
```
```
