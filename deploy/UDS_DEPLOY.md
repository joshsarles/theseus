# THESEUS — UDS / Zarf / Pepr deploy (reproduce steps)

Real Defense Unicorns tooling: **Zarf** (airgap package + SBOM + signature) and **Pepr**
(admission enforcement), running the hardened `theseus-edge:0.1.0` image with an
offline-verifiable tamper-evident record. Tested 2026-06-17 on macOS arm64.

For captured proof of a run, see `deploy/UDS_DEPLOY_EVIDENCE.md`.

> Work is confined to `deploy/` + the cluster. `frontend/` and `demo/`/`referee/`
> internals are read/copied, never modified.

---

## 0. Prereqs (versions used)

```
uds v0.32.0 · zarf v0.78.0 · pepr 1.2.1 · cosign v3.1.1
k3d v5.9.0 (k3s v1.35.5) · docker 29.5.3 · kubectl v1.34.1 · node 25 / npm 11
```

Install (macOS): `brew install defenseunicorns/tap/uds zarf cosign k3d`.
Pepr is invoked via `npx` from `deploy/uds/pepr` (pinned `pepr@1.2.1`).

---

## 1. Build + airgap-import the image (no registry pull)

```bash
cd /Users/force/Developer/Theseus

# Build the hardened, non-root edge image (demo/ loop + referee/ record + real UCI #316 baked in).
docker build -f deploy/Containerfile -t theseus-edge:0.1.0 .

# Create an isolated cluster (does NOT touch any existing cluster/context).
k3d cluster create theseus --servers 1 --agents 0 --no-lb \
  --k3s-arg "--disable=traefik@server:0" --wait
kubectl config use-context k3d-theseus

# Side-load the image into the cluster's containerd — airgap, no pull at deploy time.
k3d image import theseus-edge:0.1.0 -c theseus
docker exec k3d-theseus-server-0 crictl images | grep theseus   # confirm present
```

---

## 2. Deploy the in-cluster model-delivery loop (real Job)

```bash
kubectl apply -f deploy/uds/manifests/namespace.yaml
kubectl apply -f deploy/uds/manifests/theseus-job-image.yaml
kubectl -n theseus wait --for=condition=complete job/theseus-loop --timeout=180s
kubectl -n theseus logs job/theseus-loop          # stage->retrain->promote + offline verify PASS
```

Expect: `record verify: ✅ PASS — 3 leaves` and `PASS PASS — 3 leaves` (separate offline verify).

---

## 3. Pepr admission — deploy + prove DENY/ADMIT (the money proof)

```bash
cd deploy/uds/pepr
npm ci                        # one-time (node_modules may already be present)
npx pepr build                # -> dist/ (module manifest + helm chart)

# The controller image (ghcr.io/defenseunicorns/pepr/controller:v1.2.1) must be in the cluster.
# On a connected host `npx pepr deploy --yes` pulls it. For airgap, pre-import it:
#   NOTE: pull the arm64 manifest BY DIGEST to avoid a broken multi-arch index on import:
docker pull ghcr.io/defenseunicorns/pepr/controller@sha256:2f6b2b2d2083b743e5c29292137c14388a0b6c0ddcefe1b35d1f42e3e5358c77
docker tag  ghcr.io/defenseunicorns/pepr/controller@sha256:2f6b2b2d2083b743e5c29292137c14388a0b6c0ddcefe1b35d1f42e3e5358c77 \
            ghcr.io/defenseunicorns/pepr/controller:v1.2.1
k3d image import ghcr.io/defenseunicorns/pepr/controller:v1.2.1 -c theseus

npx pepr deploy --image ghcr.io/defenseunicorns/pepr/controller:v1.2.1 --yes
kubectl get validatingwebhookconfigurations | grep pepr     # webhook registered

# Prove DENY (each must be rejected by admission):
cd /Users/force/Developer/Theseus
kubectl apply -f deploy/uds/admission-tests/bad-privileged.yaml   # privileged+root -> DENIED (rails 2,3)
kubectl apply -f deploy/uds/admission-tests/bad-root.yaml         # root -> DENIED (rail 3, runAsNonRoot)
kubectl apply -f deploy/uds/admission-tests/bad-noapproval.yaml   # autonomy w/o human -> DENIED (rail 1)
kubectl apply -f deploy/uds/admission-tests/bad-hostpath.yaml     # hostPath escape -> DENIED (rail 3)

# Prove ADMIT (compliant must succeed):
kubectl apply -f deploy/uds/admission-tests/good-compliant.yaml   # ADMITTED
kubectl apply -f deploy/uds/admission-tests/good-approved.yaml    # autonomy WITH human approval -> ADMITTED
kubectl -n theseus delete pod good-compliant good-approved        # cleanup
```

---

## 4. Zarf airgap package + SBOM + cosign signature (ATO artifacts)

```bash
cd /Users/force/Developer/Theseus
mkdir -p deploy/uds/dist/keys deploy/uds/dist/sbom

# Demo signing keypair (empty passphrase = DEMO ONLY; use a real KMS/HSM key for prod).
( cd deploy/uds/dist/keys && COSIGN_PASSWORD="" cosign generate-key-pair )

# Create the SIGNED airgap package; Zarf auto-generates the SBOM (Syft) and signs (embedded cosign).
COSIGN_PASSWORD="" zarf package create deploy/uds/image-package -o deploy/uds/dist \
  --signing-key deploy/uds/dist/keys/cosign.key \
  --sbom-out deploy/uds/dist/sbom --confirm

# Verify the package signature with the public key:
zarf package inspect definition \
  deploy/uds/dist/zarf-package-theseus-edge-arm64-0.1.0.tar.zst \
  --key deploy/uds/dist/keys/cosign.pub          # -> "Verified OK", signed: true

# Standalone cosign blob signature (offline / airgap — no Rekor transparency log):
cosign signing-config create --out deploy/uds/dist/keys/signing-config.json
PKG=deploy/uds/dist/zarf-package-theseus-edge-arm64-0.1.0.tar.zst
COSIGN_PASSWORD="" cosign sign-blob --yes --key deploy/uds/dist/keys/cosign.key \
  --signing-config deploy/uds/dist/keys/signing-config.json --bundle "$PKG.cosign.bundle" "$PKG"
cosign verify-blob --key deploy/uds/dist/keys/cosign.pub --insecure-ignore-tlog=true \
  --bundle "$PKG.cosign.bundle" "$PKG"           # -> "Verified OK"
```

SBOM lands in `deploy/uds/dist/sbom/theseus-edge/` (Syft JSON + HTML viewer, 100 packages).

`zarf package deploy <pkg> --confirm` deploys the package through an initialized cluster
(requires `zarf init`, which pulls the zarf-init package from GHCR). For the pure airgap
side-load demo above, the `k3d image import` + `kubectl apply` path (steps 1–2) is used and
needs no `zarf init`.

---

## 5. Full UDS Core path (when GHCR is reachable / mirrored)

The fullest DU story adds Istio mTLS, Keycloak SSO/RBAC, Falco, the observability stack, and
the **UDS Operator** that reconciles the `Package` CR (`deploy/uds/manifests/uds-package.yaml`)
into NetworkPolicy default-deny egress + Istio routes.

```bash
# Creates a k3d cluster AND deploys uds-core (Istio + Keycloak + Pepr operator):
uds deploy k3d-core-slim-dev:1.6.0 --confirm
# then deploy the Theseus bundle over it (uncomment core-slim-dev in deploy/uds/uds-bundle.yaml):
zarf package create deploy/uds -o deploy/uds/dist --confirm     # the ConfigMap-over-base package
uds create deploy/uds -o deploy/uds/dist --confirm
uds deploy deploy/uds/dist/uds-bundle-theseus-*.tar.zst --confirm
```

> On this box (2026-06-17) the `k3d-core-slim-dev` pull STALLED on GHCR rate-limiting
> (uds-k3d-dev, 729 MB, 0 bytes/90s), so the slim-dev platform layer is NOT deployed here.
> Use a registry mirror / authenticated GHCR / pre-warmed `~/.uds-cache` to avoid the throttle.
> See `deploy/UDS_DEPLOY_EVIDENCE.md` → "REAL vs PENDING".

---

## Teardown

```bash
k3d cluster delete theseus
k3d cluster delete uds        # leftover from the stalled slim-dev attempt (harmless)
# does NOT touch the pre-existing kind-force cluster
```

## Files in this deploy

```
deploy/Containerfile                          hardened theseus-edge image (pre-existing)
deploy/uds/manifests/namespace.yaml           theseus namespace (pre-existing)
deploy/uds/manifests/theseus-job-image.yaml   REAL-IMAGE in-cluster loop+verify Job  [added]
deploy/uds/image-package/zarf.yaml            self-contained real-image Zarf package [added]
deploy/uds/image-package/manifests/           namespace + job copies for the package [added]
deploy/uds/admission-tests/*.yaml             Pepr DENY/ADMIT proof manifests        [added]
deploy/uds/pepr/                              Pepr module (theseus-policies, pre-existing; rebuilt)
deploy/uds/dist/                              package + SBOM + keys + signatures     [generated]
deploy/UDS_DEPLOY.md / UDS_DEPLOY_EVIDENCE.md this doc + captured evidence            [added]
```
