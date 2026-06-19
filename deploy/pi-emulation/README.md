# Emulate the 2 Raspberry Pi UUV nodes on the Mac (no hardware)

Run **both** edge UUV nodes as containers on the laptop (Node 3) so development and
the demo work with the Pis powered off. The Mac (Apple silicon, **arm64**) and the Pi 5
(**arm64** Bookworm) share an instruction set, so the *exact* Pi receiver image runs
**natively** — no QEMU cross-architecture emulation, no slowdown. This is why we
containerize the workload instead of emulating a whole Raspberry Pi OS: the receiver is
pure userspace (FastAPI + River, no GPIO/kernel modules), and QEMU has no `raspi5`
machine type anyway.

```
 ┌─────────────────────────── this Mac (Node 3) ───────────────────────────┐
 │  MLflow registry :5050  ◄───────────────┬───────────────┐               │
 │  (models + accreditation evidence)      │               │               │
 │                                  host.docker.internal:5050               │
 │   ┌──────────────────────┐      ┌───────┴────────┐  ┌────┴───────────┐   │
 │   │ uuv1-node  :54321    │      │ models:/uuv1_  │  │ models:/uuv2_  │   │
 │   │ MACHINERY            │──────▶ anomaly_deploy │  │ anomaly_deploy │   │
 │   │ (analytics:latest)   │      │  @production   │  │  @production   │   │
 │   ├──────────────────────┤      └────────────────┘  └────────────────┘   │
 │   │ uuv2-node  :54322    │              ▲ load           ▲ load          │
 │   │ CONTACTS             │──────────────┘                │               │
 │   └──────────────────────┘     both on the `fleet` bridge network        │
 └──────────────────────────────────────────────────────────────────────────┘
```

## Quick start

```bash
bash deploy/pi-emulation/up.sh --feed         # both nodes + live synthetic feed (1 rec/30s)
curl http://127.0.0.1:54321/health            # UUV-1 (MACHINERY)
curl http://127.0.0.1:54322/health            # UUV-2 (CONTACTS)
curl http://127.0.0.1:54321/history | jq '.[-1]'   # latest scored record (active_anomaly_score)
bash deploy/pi-emulation/down.sh              # stop everything
```

`up.sh` tags the image, ensures MLflow `:5050` is up, starts both nodes, and waits until
each has loaded its model and reports healthy. `--feed` also starts one synthetic streamer
per node (the same `gen_synthetic_sensors.py` that ran on the Pis). Use `--interval=2` for
a livelier feed during a live demo.

## How the image gets here

The container image is the **byte-identical** image off the Pi (receiver.py is the same
sha on pi1 and pi2, so one image serves both nodes — only the mounted config differs):

```bash
ssh pi2 'podman save analytics:latest' | docker load        # Pi must be on
docker tag localhost/analytics:latest analytics:latest
```

**Rebuild from source instead** (no Pi needed — fully offline, ~arm64 native):

```bash
cd serve/receiver
docker build -f ../../deploy/mlflow/analytics-base.Dockerfile -t analytics-base:latest .
docker build -f Dockerfile -t analytics:latest .
```

## Per-node config

Both containers run one image; each mounts its own `config.yml` (via `RECEIVER_CONFIG`):

| Node | Host port | In-container | Model loaded | Config |
|---|---|---|---|---|
| `uuv1-node` (MACHINERY) | `54321` | `54321` | `uuv1_anomaly_deploy@production` | `config.uuv1.yml` |
| `uuv2-node` (CONTACTS)  | `54322` | `54321` | `uuv2_anomaly_deploy@production` | `config.uuv2.yml` |

The only delta vs the real Pi configs: `mlflow.host` is `host.docker.internal` (the Mac
host) instead of the LAN IP.

## The two things that make the model load (vs silent baseline fallback)

The Pi's 4-condition recipe (see `docs/setup/PI_NODES.md`) carries over, plus one
Mac-specific fix:

1. **`MLFLOW_TRACKING_URI` in the container env** → set in compose (proxied-artifact download).
2. **MLflow Host-header allowlist** — MLflow 3.x rejects the `host.docker.internal` Host
   header as a "DNS rebinding attack" (the Pis worked because a raw LAN IP matches MLflow's
   private-IP default). `deploy/mlflow/run.sh` now exports `MLFLOW_SERVER_ALLOWED_HOSTS`
   covering localhost + RFC-1918 + `host.docker.internal` (+ `*.orb.local` for OrbStack).
   Restart MLflow after pulling this change: `bash deploy/mlflow/run.sh`.

## Want per-node DNS (`uuv1-node.orb.local`) instead of ports?

Optional upgrade: **OrbStack** gives every container a zero-config `<name>.orb.local`
domain and faster I/O. `brew install orbstack`, then the same compose works; reach nodes
by name and the Mac host as `host.orb.internal`. (OrbStack is commercial-paid for Force;
Docker Desktop — already installed here — works fine via `host.docker.internal`.)

## Detection quality

`active_anomaly_score` cleanly separates normal vs anomaly: **normal ~0.2, anomaly ~0.9**
on the live stream. The detector is a streaming per-feature running-z-score model
(`RunningZScoreDetector` in `register_pickle_model.py`) — anomaly score = max |z| across
the sensor channels, squashed to [0,1). It replaced HalfSpaceTrees, which gave near-zero
separation here (AUC ~0.65; scores stuck at ~0.98 for normal *and* anomaly). Current
registered-model eval:

| Model | precision@k | F1 | false-alarm | ROC-AUC |
|---|---|---|---|---|
| `uuv1_anomaly_deploy` | 0.96 | 0.96 | 0.013 | 0.9995 |
| `uuv2_anomaly_deploy` | 0.87 | 0.87 | 0.036 | 0.94 |

Bonus for T&E / accreditation: the score is **explainable** — it points at the specific
sensor channel that deviated and by how many σ, rather than an opaque tree-mass score.
