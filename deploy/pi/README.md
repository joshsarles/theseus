# THESEUS — Raspberry Pi edge-node deploy bundle

One command pushes a ship-system **edge node** onto a Pi-class device (arm64, CPU-only,
offline). The node serves its system's model locally **and reports UP to the ship brain**,
so the brain's CIC dashboard shows that system as a real, live edge node.

```
ship brain (Tier-1)  demo/api.py :8077  ── POST /api/node-report ◄── report_up.py
        ▲                                                              ▲
        │ aggregates fresh node reports into /api/state.systems        │ runs ON the Pi,
        │ (live + version + health, honest; stale → standby)           │ beside model_server.py
        └────────────────── one ship, all systems ────────────────────┘
```

## What lands on the Pi

`install.sh` stages a flat bundle to `REMOTE_DIR` (default `/opt/theseus-edge`):

| Path on Pi | What | Why |
|---|---|---|
| `serve/model_server.py` + `model_core.py` | local inference server (`/health /version /predict /reload`) | serves the model at the edge, CPU-only, stdlib HTTP |
| `serve/report_up.py` | edge→brain reporting beat | reports UP `{node_id, system, version, framework, health, last_good, leaf_hashes}` |
| `serve/explain_local.py` | NV063 explainer (local Qwen 2.5 3B via goose) | plain-language alerts ON the Pi; template fallback if LLM down |
| `referee/` | tamper-evident record library | every model load / decision sealed locally |
| `demo/_record.py` | record sealer | used by server + explainer |
| `demo/models/current/` | a servable model dir (`meta.json` + `model.bin`) | gives `/health` a real version to report |
| `models/onnx/*.onnx` + `infer.py` | the ONNX model(s) for `<system>` | the team's real edge inference path (machinery→CBM, contacts→autoencoder) |
| `node.env` | this node's identity/config | the only host-specific file; regenerated each deploy |
| `edge_run.sh`, `theseus-edge.service.tmpl`, `requirements-pi.txt` | launcher + systemd unit + deps | systemd if available, else nohup |

## Prerequisites on the Pi (offline)

- **Python 3** (any 3.10+) — already present on Raspberry Pi OS / Ubuntu arm64.
- The model server **and** report-up run on the **standard library alone** when the
  served model is the `stdlib-ols` flavor — so a bare Pi with no wheels still serves +
  reports up.
- **Optional deps** (only for the ONNX infer path and to unpickle an sklearn `model.bin`):
  `onnxruntime`, `numpy`, `scikit-learn`. Pre-stage them offline:
  ```bash
  # on an internet-connected arm64 box (or with --platform), download wheels:
  pip download -r deploy/pi/requirements-pi.txt -d deploy/pi/wheels \
      --platform manylinux2014_aarch64 --only-binary=:all: --python-version 3.11
  # they ride along in the bundle; edge_run.sh installs with: pip install --no-index --find-links wheels
  ```
- **goose + Qwen 2.5 3B** (for `explain_local.py`) — already on Pi-1. If absent, the
  explainer auto-falls back to the deterministic template; deploy does not depend on it.

## Deploy (the one command)

```bash
# from a full THESEUS checkout on your workstation:
deploy/pi/install.sh '<user>@<host>' <system> [brain-url]

# examples:
deploy/pi/install.sh pi@pi1.local machinery http://brain.ship:8077
deploy/pi/install.sh ubuntu@10.0.0.7 contacts http://100.x.y.z:8077   # Tailscale brain
```

> **SSH auth is operator-owned.** `pi1.local`'s username/key was unknown at build time
> (possible reimage), so this is **parameterized** — pass the real `user@host`. Set up
> key auth first (`ssh-copy-id <user>@<host>`), or pass options via `SSH_OPTS`
> (e.g. `SSH_OPTS='-i ~/.ssh/pi_key -o StrictHostKeyChecking=accept-new'`).

### Useful overrides (env)
```bash
NODE_ID=pi1-machinery \
EDGE_PORT=8080 \
REMOTE_DIR=/opt/theseus-edge \
REPORT_INTERVAL=15 \
SSH_OPTS='-i ~/.ssh/pi_key' \
deploy/pi/install.sh pi@pi1.local machinery http://brain.ship:8077
```

## What `install.sh` does (over SSH, idempotent)

1. Stages the bundle locally (per-system model selection), writes `node.env`.
2. `rsync` (or `tar`-over-ssh if rsync is absent) to `REMOTE_DIR` — re-running updates
   files in place, no duplication.
3. Runs `./edge_run.sh install` **on the Pi**, which decides:
   - **systemd present + sudo** → installs `/etc/systemd/system/theseus-edge-<system>.service`
     (renders the template), `daemon-reload`, `enable`, `restart`. Survives reboot.
   - **otherwise** → `nohup` launch of model server + report-up, PIDs under `.run/`.
4. Smoke-checks local `/health` and prints PASS/WARN.

## Verify on the brain

```bash
curl -s http://brain.ship:8077/api/state | python3 -m json.tool | grep -A8 '"machinery"'
# expect: "live": true, the node block with model_version + health, severity nominal/warning
curl -s http://brain.ship:8077/api/state | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["nodes"])'
```

## Operate (on the Pi)

```bash
ssh <user>@<host> 'cd /opt/theseus-edge && ./edge_run.sh status'   # local /health
ssh <user>@<host> 'cd /opt/theseus-edge && ./edge_run.sh logs'     # journald or .run/*.log
ssh <user>@<host> 'cd /opt/theseus-edge && ./edge_run.sh once'     # one-shot report up
ssh <user>@<host> 'cd /opt/theseus-edge && ./edge_run.sh stop'     # stop (systemd or nohup)

# generate NV063 alerts on the Pi (local Qwen 2.5 3B via goose; template fallback):
ssh <user>@<host> 'cd /opt/theseus-edge && python3 serve/explain_local.py --n 3'
```

## DDIL / offline behavior (by design)

- The edge **keeps serving locally** whether or not the brain is reachable. `report_up`
  only reports; it never gates inference.
- Brain unreachable → `report_up` logs, keeps last-good report, retries with bounded
  backoff, forever. The node never goes silent and never crashes.
- A node that goes dark **expires** at the brain (`TTL_SECONDS`, default 60s) → its system
  falls back to **standby**. Honest: no fresh report ⇒ not shown green.
- If the local model server itself is down, `report_up` still reports `health=down` so the
  brain shows the node **degraded**, not missing.
