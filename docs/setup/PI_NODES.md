# Tier-2 setup — the 2 Raspberry Pi 5 (4GB) system-component nodes
*William's lane. Stands up the 2 Pis as the shipboard system-components feeding the Tier-1 brain (Blackwell-emulated). 4GB ⇒ small models only; the Pis do inference/detection, NOT the MLflow server (that's Tier-1).*

## The mapping (2 Pis = 2 organs)
| Node | Organ | Runs | Model |
|---|---|---|---|
| **Pi-1** | **MACHINERY / HM&E** | `demo/update_model.py` (serves the latest model) | CBM gas-turbine decay (UCI #316) |
| **Pi-2** | **CONTACTS** | `demo/ais_pol.py` | AIS Pattern-of-Life (MarineCadastre; live SDR later) |

## Node addresses + SSH access
| Node | Host | User | Connect |
|---|---|---|---|
| **Pi-1** (UUV-1 · MACHINERY) | `10.10.3.244` | `pi1` | `ssh pi1@10.10.3.244` |
| **Pi-2** (UUV-2 · CONTACTS)  | `10.10.2.173` | `pi2` | `ssh pi2@10.10.2.173` |

**Password is NOT in this public repo** (it would be exposed on GitHub) — it's in `deploy/pi/.pi-access.md` (gitignored, on the Node-3 machine) and the team channel. The edge receiver listens on **:54321**.

### Pi → Node-3 MLflow connectivity (the ":5050 connection refused" fix)
Two things must both be true:
1. **Node 3 binds all interfaces** — `deploy/mlflow/run.sh` now launches `mlflow server --host 0.0.0.0 --port 5050` (was `127.0.0.1`, which only accepted localhost). ✓ done.
2. **The Pi points at the Node-3 LAN IP, not `localhost`** — in the Pi's receiver `config.yml`, set `mlflow.host` to the **Node-3 IP** (NOT `localhost` — that makes the Pi connect to itself → connection refused). **Current Node-3 IP: `10.10.2.162`** (interface `en13`; DHCP can change it — re-check on the Mac with `ipconfig getifaddr en13` or `route -n get default`). Both Pis are on the same `10.10.0.0/22` and ping the Mac sub-ms.

Verify from a Pi: `curl http://10.10.2.162:5050/health` → expect `200`. Then the receiver loads `models:/uuv1_anomaly_deploy@production`.

## 1. Flash + base (both Pis)
- **Raspberry Pi OS 64-bit (Bookworm)**, headless, SSH enabled, unique hostnames `theseus-pi1` / `theseus-pi2`, static IPs or mDNS on the same switch/LAN as the Tier-1 box.
- Update + tools:
  ```bash
  sudo apt update && sudo apt -y full-upgrade
  sudo apt -y install podman git python3 python3-venv python3-pip
  python3 --version   # aim for 3.14.x; if distro lags, a 3.14 venv or pyenv is fine
  ```
- Rootless Podman (no root containers — matches the rails):
  ```bash
  loginctl enable-linger $USER
  podman info | grep -i rootless
  ```

## 2. Get the repo + verify the loop (both Pis)
```bash
git clone https://github.com/joshsarles/theseus.git && cd theseus
python3 -m venv .venv && . .venv/bin/activate
pip install scikit-learn         # optional; stdlib fallback works on 4GB if pip is slow
bash demo/run.sh                 # Stage->Retrain->Update on the committed real UCI #316; record verify PASS
```
If `run.sh` is green, the node can train/serve/seal locally — disconnected-capable by construction.

## 3. Point at Tier-1 (the Blackwell-emulated ship brain), when present
```bash
export MLFLOW_TRACKING_URI=http://<tier1-host>:5050   # Blackwell box or the laptop running MLflow
```
With this set, `retrain.py` logs to the central registry; without it, the node works fully local (DDIL).

## 4. Per-node run
- **Pi-1 (machinery):** `python3 demo/update_model.py` — pulls the latest registered model into `models/current`, keeps `models/previous` for rollback, seals the promotion. On a real ship this node taps the HM&E bus; for the demo it serves the CBM model.
- **Pi-2 (contacts):** copy a MarineCadastre slice to `data/datasets/marinecadastre_us/` (gitignored — `scp` it over, it's too big for 4GB to fetch live easily), then `python3 demo/ais_pol.py --rows 800000`. (Live RTL-SDR cold-start comes later — see the SDR plan.)
- **Watchstander board:** `python3 demo/show.py` renders the sealed record (machinery health + contacts + record PASS).

## 5. DDIL beat (the demo money shot)
1. Both Pis green, models serving, record verifies.
2. **Pull the network cord** (unplug the switch uplink / unset `MLFLOW_TRACKING_URI`).
3. Both Pis keep serving the **last-good** model; `update_model.py` still promotes from the **local** registry; the record still verifies — no shore needed.
4. Inject a bad model → local **rollback** to `models/previous` works with no shore.
5. Reconnect → resync. (The `deploy/ddil_beat.sh` script automates this — see `deploy/`.)

## 4GB gotchas (Pi 5, 4GB)
- **Don't run the MLflow server or Triton on a Pi** — those are Tier-1 (Blackwell/GPU). The Pi is inference/detection only.
- Keep `--rows` modest on Pi-2 for AIS (≤~800k) to stay within 4GB; the detector streams but track-building holds state.
- If an edge LLM is ever needed on a Pi, use a **small GGUF (≤~1.5B, Q4)** via llama.cpp — not vLLM/Triton.
- Swap on: a small zram/swap helps headroom for sklearn training on 4GB.

## Networking
Both Pis + the Tier-1 host on one switch. mDNS (`theseus-pi1.local`) or static IPs. The shared record / cross-node publish (Zenoh) is a later step; for the demo, each Pi keeps its own local record and `show.py` renders it.
