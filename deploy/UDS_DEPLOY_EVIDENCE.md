# THESEUS on Defense Unicorns tooling — DEPLOY EVIDENCE

**Captured:** 2026-06-17, on macOS (Apple Silicon, arm64), Docker Desktop.
**What this proves:** THESEUS deploys with REAL Defense Unicorns technology — real
`zarf` (airgap package + SBOM + signature) and real `pepr` (admission enforcement)
— with the hardened `theseus-edge:0.1.0` image running the model-delivery loop and
an offline-verifiable tamper-evident record, all in-cluster.

This file is verbatim captured output. It is deliberately honest about what is
fully real vs. what is network-blocked (see the REAL vs PENDING section at the end).

---

## Tool versions (all real, installed on this box)

```
uds     v0.32.0          (defenseunicorns/uds-cli)
zarf    v0.78.0          (zarf-dev/zarf)
pepr    1.2.1            (defenseunicorns/pepr)
cosign  v3.1.1           (sigstore/cosign)
k3d     v5.9.0           (k3s v1.35.5)
docker  29.5.3
kubectl v1.34.1
node    25.2.1 / npm 11.7.0
python  3.14.4 (host) ; image runs python 3.14.6
```

---

## 1. Cluster — REAL k3d cluster `theseus`

UDS Core slim-dev (`uds deploy k3d-core-slim-dev:1.6.0`) was attempted first (the
fullest DU story: Istio + Keycloak + Pepr UDS Operator). It STALLED on the GHCR
pull of `uds-k3d-dev` (729 MB layer; 0 bytes in 90s — anonymous GHCR rate-limit).
Documented and fell back to the realest deployable path: plain k3d + the real
DU tools (Zarf + Pepr). See REAL vs PENDING.

```
$ k3d cluster create theseus --servers 1 --agents 0 --no-lb \
    --k3s-arg "--disable=traefik@server:0" --wait
Cluster 'theseus' created successfully!

$ kubectl --context k3d-theseus get nodes
NAME                   STATUS   ROLES           AGE   VERSION
k3d-theseus-server-0   Ready    control-plane   ...   v1.35.5+k3s1
```

Final `kubectl get pods -A`:

```
NAMESPACE     NAME                                                         READY   STATUS      RESTARTS   AGE
kube-system   coredns-8db54c48d-pc64h                                      1/1     Running     0          8m40s
kube-system   local-path-provisioner-5d9d9885bc-l4ff9                      1/1     Running     0          8m40s
kube-system   metrics-server-786d997795-gpbd8                              1/1     Running     0          8m39s
pepr-system   pepr-17ecd300-cc52-4e4d-929d-cb306db1e5a3-5b88b77d5f-bkv5z   1/1     Running     0          4m44s
pepr-system   pepr-17ecd300-cc52-4e4d-929d-cb306db1e5a3-5b88b77d5f-sp9h7   1/1     Running     0          4m44s
theseus       theseus-loop-bbhx5                                           0/1     Completed   0          5m7s
```

---

## 2. Image — REAL airgap side-load (no registry pull)

`theseus-edge:0.1.0` (built from `deploy/Containerfile`, hardened, non-root) and the
Pepr controller were side-loaded into the cluster's containerd via `k3d image import`
— true airgap shape, no pull at deploy time.

```
$ docker build -f deploy/Containerfile -t theseus-edge:0.1.0 .   # (pre-built, verified)
$ k3d image import theseus-edge:0.1.0 -c theseus
Successfully imported 1 image(s) into 1 cluster(s)

$ docker exec k3d-theseus-server-0 crictl images | grep -E 'theseus|pepr'
docker.io/library/theseus-edge                 0.1.0    76cda58c696ab   122MB
ghcr.io/defenseunicorns/pepr/controller        v1.2.1   455de90999b0a   163MB
```

Note: the Pepr controller multi-arch index had a missing amd64 manifest blob from a
throttled pull; resolved by pulling the arm64 manifest by digest
(`@sha256:2f6b2b2d2083...`) and importing the single-arch image. See UDS_DEPLOY.md.

---

## 3. In-cluster model-delivery loop — REAL, verify PASS

The `theseus-loop` Job (`deploy/uds/manifests/theseus-job-image.yaml`) runs the baked
image with `imagePullPolicy: Never` (hard airgap guarantee). It ran and **Completed
in 7 seconds**. Verbatim logs:

```
================ THESEUS model-delivery loop (in-cluster, baked image) ================
THESEUS demo · STEP 1 — Stage Operational Data
  using cached staged data at demo/data/staged.csv
  sealed data_staged · rows=11934 · sha256=2566106b4fa4…

THESEUS demo · STEP 2 — Retrain
  framework=sklearn  version=v1  RMSE=0.00382
  registered -> demo/registry/theseus-cbm/v1  (sha256=ea177eb6118a…)
  sealed model_trained

THESEUS demo · STEP 3 — Update local model (edge node)
  promoted v1 -> models/current  (RMSE=0.003823)
  sealed model_promoted
  record verify: ✅ PASS — 3 leaves, head eda084884c1d…, merkle cfbcf74367f0…

----- sealed record: out/record/bundle.json -----
{
  "bundle_kind": "referee-proof-bundle/reference-v0",
  "leaf_count": 3,
  "chain_head": "eda084884c1dae0c757ba4a4a8fa8402bb225d27647a675d740a18c5760a3e84",
  "merkle_root": "cfbcf74367f01fd3377929a773415f23c5fd57c965ad40089b483f2584b8c9db",
  "rfc3161": null,
  "tamper_evident_not_tamper_proof": true,
  "generated_unix": 1781739218.5221705
}
----- record leaves (idx kind:obs_id) -----
  [0] data_staged:staged.csv
  [1] model_trained:theseus-cbm:v1
  [2] model_promoted:theseus-cbm:v1

----- offline verify (third-party-runnable, no trust in us) -----
PASS PASS — 3 leaves, head eda084884c1d…, merkle cfbcf74367f0…
=======================================================================================
```

- Real UCI #316 naval gas-turbine CBM data (11,934 rows, CC BY 4.0), staged offline.
- Real model retrain (scikit-learn GradientBoosting, RMSE 0.00382), promoted with rollback kept.
- Real SHA-256 hash-chain record (3 leaves + merkle root), offline-verified PASS as a
  SEPARATE step (`theseus verify`, non-zero exit would fail the Job).

```
$ kubectl --context k3d-theseus -n theseus get job theseus-loop
NAME           STATUS     COMPLETIONS   DURATION   AGE
theseus-loop   Complete   1/1           7s         ...
```

---

## 4. Pepr admission — THE MONEY PROOF (real DENY + real ADMIT)

Pepr module `theseus-policies` deployed to the cluster (controller image side-loaded):

```
$ npx pepr deploy --image ghcr.io/defenseunicorns/pepr/controller:v1.2.1 --yes
Module deployed successfully
Deployment ... rolled out: 2 of 2 replicas are available

$ kubectl --context k3d-theseus get validatingwebhookconfigurations | grep pepr
pepr-17ecd300-cc52-4e4d-929d-cb306db1e5a3   1   ...
# watches: pods, pods/ephemeralcontainers
```

### DENIED (4 violations, verbatim — admission rejected each)

```
# 1. privileged + root pod  (deploy/uds/admission-tests/bad-privileged.yaml)
Error from server: admission webhook "pepr-....pepr.dev" denied the request:
  THESEUS rail 2 (contained): container "evil" requests privileged — forbidden.
  Privileged pods can reconfigure host networking and escape egress controls.;
  THESEUS rail 3 (hardened): container "evil" is privileged — forbidden.

# 2. root (no runAsNonRoot)  (deploy/uds/admission-tests/bad-root.yaml)
Error from server: admission webhook "pepr-....pepr.dev" denied the request:
  THESEUS rail 3 (hardened): container "rooty" must set
  securityContext.runAsNonRoot: true (pod- or container-level). AC-6 least privilege.

# 3. autonomy action w/o human approval  (deploy/uds/admission-tests/bad-noapproval.yaml)
Error from server: admission webhook "pepr-....pepr.dev" denied the request:
  THESEUS rail 1 (human-in-command): pod declares action "model-promote" but has no
  human approval. Set annotation "theseus.forceos.ai/human-approved-by" ...
  Theseus drafts the call; a human approves it.

# 4. hostPath escape  (deploy/uds/admission-tests/bad-hostpath.yaml)
Error from server: admission webhook "pepr-....pepr.dev" denied the request:
  THESEUS rail 3 (append-only/hermetic): volume "hostescape" is a hostPath (/etc).
  hostPath is forbidden on Theseus pods ...
```

### ADMITTED (compliant — proves it is not blanket-denying)

```
# fully compliant theseus pod  (deploy/uds/admission-tests/good-compliant.yaml)
pod/good-compliant created

# autonomy action WITH human approval  (deploy/uds/admission-tests/good-approved.yaml)
pod/good-approved created
```

Rails enforced at admission: human-in-command (rail 1), contained/no-egress posture +
no privileged/hostNetwork (rail 2), non-root + readOnlyRootFilesystem + drop-ALL-caps +
no-priv-escalation + no-hostPath append-only (rail 3). These are AC-6 / SC-7 / AU-9
evidence — admission-time enforcement, not an ATO.

---

## 5. Death-proof artifacts — REAL Zarf SBOM + REAL signature

### Zarf airgap package (real, contains the image + manifests)

```
$ zarf package create deploy/uds/image-package -o deploy/uds/dist \
    --signing-key deploy/uds/dist/keys/cosign.key --sbom-out deploy/uds/dist/sbom --confirm
package signed successfully
writing package to disk path=deploy/uds/dist/zarf-package-theseus-edge-arm64-0.1.0.tar.zst
```

Artifact: `deploy/uds/dist/zarf-package-theseus-edge-arm64-0.1.0.tar.zst` (117 MB)
  sha256 `05cf2d418dcbfdf7fa7047b4175b5d85834e742de1fc56ff2182baa414547992`
  aggregateChecksum (in package) `f166313d20b3...`, built by zarf v0.78.0, `signed: true`.

### SBOM (the ATO supply-chain artifact — generated by Zarf via Syft)

Path: `deploy/uds/dist/sbom/theseus-edge/`
  - `docker.io_library_theseus-edge_0.1.0.json` (Syft JSON, schema 16.1.3, descriptor `zarf v0.78.0`)
    sha256 `f13d26d493cc39055aa2bcff4bb48fded7c1d6db6099307f3c2be2d08820fae9`
  - `sbom-viewer-docker.io_library_theseus-edge_0.1.0.html` (human-viewable)
  - `compare.html`

```
total packages in image SBOM: 100   (deb: 87, python: 6, binary: 7)
  python scikit-learn 1.7.2
  python numpy 2.4.6
  python scipy 1.17.1
  python joblib 1.5.3
  python threadpoolctl 3.6.0
  binary python 3.14.6
```

### Signature — REAL cosign, signed AND verified (offline / airgap posture)

Zarf-native (cosign embedded) signature verified with the public key:

```
$ zarf package inspect definition <pkg> --key deploy/uds/dist/keys/cosign.pub
Verified OK
  signed: true
  reason: This package contains a bundle format signature ... Zarf v0.71.0 or later
```

Standalone cosign blob signature (offline signing-config, no Rekor transparency log):

```
$ cosign sign-blob --key cosign.key --signing-config signing-config.json \
    --bundle <pkg>.cosign.bundle <pkg>
Wrote bundle to file ...zarf-package-theseus-edge-arm64-0.1.0.tar.zst.cosign.bundle

$ cosign verify-blob --key cosign.pub --insecure-ignore-tlog=true \
    --bundle <pkg>.cosign.bundle <pkg>
Verified OK

# negative control — tampered (truncated) bytes are correctly REJECTED:
$ cosign verify-blob ... /tmp/tampered.tar.zst
Error: failed to verify signature: ... invalid signature
```

Artifacts:
  - `deploy/uds/dist/keys/cosign.pub` / `cosign.key` (DEMO keypair, empty passphrase — demo only)
  - `deploy/uds/dist/keys/signing-config.json` (offline signing config)
  - `deploy/uds/dist/zarf-package-theseus-edge-arm64-0.1.0.tar.zst.cosign.bundle`

---

## REAL vs PENDING (honest breakdown — no aspirational-as-built)

### REAL — verified running / produced on this box today
- **k3d cluster `theseus`** (k3s v1.35.5) — node Ready, isolated from other clusters.
- **Hardened image `theseus-edge:0.1.0`** built + side-loaded airgap (`k3d image import`), no pull at deploy.
- **In-cluster `theseus-loop` Job** — Completed (7s): real UCI #316 stage → sklearn retrain → promote
  → SHA-256 hash-chain record (3 leaves) → **offline verify PASS** as a separate step.
- **Pepr admission** (`theseus-policies`, real DU Pepr 1.2.1, 2/2 controller replicas, webhook registered):
  **4 violating pods DENIED** (privileged, root, no-human-approval, hostPath) with exact rail messages;
  **2 compliant pods ADMITTED**. This is the human-in-command / non-root / append-only proof.
- **Real Zarf airgap package** (`zarf v0.78.0`) containing the image + manifests, `signed: true`.
- **Real SBOM** (Syft via Zarf, 100 packages cataloged) — the ATO supply-chain artifact.
- **Real cosign signature** (v3.1.1) — package signed AND verified offline; tampered bytes rejected.

### PENDING / NOT DONE — and why (network-blocked, not design)
- **UDS Core slim-dev (full platform)** — Istio mTLS, Keycloak SSO/RBAC (the platform-level
  human-in-command authn), Falco, Loki/Vector, Prometheus/Grafana, and the **UDS Operator that
  reconciles the `Package` CR** (`deploy/uds/manifests/uds-package.yaml`). **NOT deployed.**
  Reason: `uds deploy k3d-core-slim-dev:1.6.0` STALLED on the GHCR pull of `uds-k3d-dev`
  (729 MB, 0 bytes in 90s — anonymous GHCR rate-limit; same throttle that broke the prior run).
  This is a bandwidth/rate-limit issue on this box, not a scaffold defect. On a connected /
  registry-mirrored host the documented `uds deploy k3d-core-slim-dev:<ver>` then
  `uds deploy <theseus-bundle>` path is unchanged. Until then:
    - The `uds.dev/v1alpha1 Package` CR is **inert** (its CRD ships with uds-core; not present here).
      Network policy / Istio mTLS / Keycloak SSO are therefore NOT enforced by the platform.
    - The egress-containment guarantee in the demo is currently the **Pepr posture rail only**
      (no pod may *declare* an escape hatch); the hard NetworkPolicy/Istio deny is the uds-core layer.
- **`zarf init`** (Zarf in-cluster registry/agent) — **not run.** Not needed for this airgap
  side-load path (images are `k3d image import`ed; `imagePullPolicy: Never`). `zarf package deploy`
  through an initialized cluster is the alternative; init pulls the zarf-init package from GHCR
  (same rate-limit risk). The `image-package` `onDeploy` wait/log actions are written for that path.
- **cosign Rekor transparency log** — intentionally skipped (offline/airgap key-based signing).
  Public-good Rekor entry would be added on a connected host for full sigstore transparency.
- **Lula compliance validations** (`lula/`) ride in the original `deploy/uds/zarf.yaml` package as
  files; Lula CLI was not exercised here (out of scope for this deploy pass).

### Leftover to clean up
- A second k3d cluster `uds` exists (created by the stalled slim-dev attempt before it hung on the
  pull). Harmless and isolated; `k3d cluster delete uds` removes it. The pre-existing `kind-force`
  cluster was NOT touched.
