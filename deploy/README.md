# THESEUS — deploy (UDS / airgap)

Packages the model-delivery loop + the AIS PoL cell + the tamper-evident record as an **airgap-deployable UDS mission app**, and enforces the rails at the cluster with a **Pepr** admission policy. This is the `deploy/` tree — it does **not** touch the existing `zarf/` referee package.

## What's here
| Path | What |
|---|---|
| `ddil_beat.sh` | **The DDIL demo** (runs now, no cluster): cord-pull → local promote, bad-update → local rollback, tamper → record snaps. `bash deploy/ddil_beat.sh` |
| `Containerfile` | The loop as one rootless OCI image (`theseus-edge`). Hardened: non-root, read-only rootfs, drop ALL caps. **Reference — see "Team" below.** |
| `entrypoint.sh` | Step dispatch (`loop`/`stage`/`retrain`/`update`/`ais_pol`/`show`). |
| `uds/zarf.yaml` | Zarf package — in-cluster Job runs the loop on real UCI #316 → sealed record → offline verify PASS (ConfigMap-over-base, mirrors referee). |
| `uds/uds-bundle.yaml` | UDS bundle wrapping the package. |
| `uds/manifests/` | the Job, namespace, and the **UDS `Package` CR** (Istio route + default-deny egress + monitoring). |
| `uds/pepr/` | **Pepr policy** — cluster-enforces the rails (human-in-command, contained/no-egress, append-only record + hardened workload). Compiles to `dist/` via `npx pepr build`. |

## Run it
```bash
# 1) the DDIL beat — no cluster, stdlib python3, ~10s
bash deploy/ddil_beat.sh

# 2) build the edge image (Podman preferred; Docker works — OCI)
podman build -f deploy/Containerfile -t theseus-edge:0.1.0 .
podman run --rm --read-only --tmpfs /work --security-opt no-new-privileges \
  --cap-drop ALL --user 65534:65534 theseus-edge:0.1.0 loop

# 3) airgap package + deploy (needs zarf/uds binaries)
zarf package create deploy/uds/ -o deploy/uds/dist --confirm
zarf init --confirm && zarf package deploy deploy/uds/dist/zarf-package-theseus-*.tar.zst --confirm

# 4) build the Pepr policy (needs node)
cd deploy/uds/pepr && npm ci && npx pepr build      # node_modules/ + dist/ are gitignored
```

## Team — how this slots into everyone's lane (contracts, not collisions)
- **Thang** owns the **production Pi analytics container**. `deploy/Containerfile` is a **verified reference** (builds, hardened, bakes the real data) to converge on — adopt or compare; the zarf Job + Pepr policy reference the loop regardless of whose image wins. Image-name contract: `theseus-edge:<tag>`.
- **William** owns the **2-Pi mesh over Tailscale**. `ddil_beat.sh` proves the *single-node* disconnected lifecycle; the *multi-node* failover across the 2 Pis over Tailscale is the **live mesh demo** (William's lane) — this script is honest that it doesn't cover that.
- **Nick** owns **MLflow** (Tier-1). The loop logs to it when `MLFLOW_TRACKING_URI` is set; offline it uses the local registry (DDIL).
- **Carolina** owns the **IL6 baseline**. Inputs for her: the `uds/pepr` controls + the `lula/` evidence the zarf carries + `docs/integration/INFERENCE_AND_FIPS.md` + `docs/compliance/IL_ROADMAP.md`.
- **Tier-1 hosts:** the **Gigabyte Ryzen 32GB** (local on-prem Tier-1 — MLflow + heavier compute) and the **NVIDIA Blackwell cloud** (GPU Tier-1 — Triton-TRT-LLM explainer). The 2 Pis are Tier-2 components.

## Rails / honest scope
Human-in-command (decision-support, **not** autonomous ship control) · SWAN-side/unclassified data only (combat air-gapped) · integrate-not-replace · tamper-**evident**, not tamper-proof · **deployable; ATO is the gate** (not "fielded"). The Pepr policy makes these cluster-enforced admission rules; it is evidence toward AC-6 / SC-7 / AU-9, not an authorization.
