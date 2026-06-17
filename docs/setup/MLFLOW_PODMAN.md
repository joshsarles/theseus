# MLflow on Podman — Theseus runbook
*The model-management spine (team objectives #2/#3/#4). Central MLflow server in a container; Pi nodes register/log/pull models; shore-side staging via the UDS bundle.*

## Run the central MLflow server (laptop / shore-side box)
```bash
# pull the image (do this BEFORE the venue internet dies — see "offline" below)
podman pull ghcr.io/mlflow/mlflow

# save dir for runs/artifacts
mkdir -p mlruns

# run the server (tracking + registry on :5000, sqlite backend)
podman run -d \
  --name mlflow-server \
  -p 5000:5000 \
  -v $(pwd)/mlruns:/mlflow \
  ghcr.io/mlflow/mlflow \
  mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///mlflow.db
```
Open `http://localhost:5000`. Pi nodes log/register against `http://<server-ip>:5000`.

## Versions (CVE-aware, per team Slack)
- **MLflow ≥ 3.11** (3.13 latest) — versions <3.11 carry a high-sev CVE.
- **Podman > 5.8.1** — a CVE affects 4.8.0–5.8.1; use the latest.

## ⚠️ Offline / airgap (the whole point — objective #4)
The venue internet dies; **pre-stage the image now**:
```bash
# on a connected box:
podman pull ghcr.io/mlflow/mlflow
podman save -o mlflow.tar ghcr.io/mlflow/mlflow
# move mlflow.tar onto the airgap box (USB / the UDS bundle), then:
podman load -i mlflow.tar
```
Or build from `python-slim` (mlflow `docker/Dockerfile.full`) if the ghcr pull is blocked. **Bundle the image + the registered models into the UDS/Zarf package** → that *is* "shore-side staging without sneakernet" (objective #4): the bundle carries the models; no hand-carried drive.

## How it maps to the Theseus objectives
- **#1 Deploy AI models at the edge:** MLflow-packaged models → Pi nodes (PyTorch → ONNX for the NPU).
- **#2 Centrally manage:** the MLflow server is the registry + tracking + monitoring of every model on every node.
- **#3 Live update from the edge:** edge users retrain/fine-tune → log a new version to the registry → promote.
- **#4 Stage from shore without sneakernet:** new model versions ride into the airgap inside the **UDS/Zarf bundle**; rollback-to-last-good stays local under DDIL.
- **The moat:** every model promotion / rollback / edge-update is sealed into the **tamper-evident record** (the loaded version is recorded, so a replay knows exactly which weights produced any decision).

## First model to put on the Pis (recommended)
Train a **gas-turbine decay/RUL model on UCI #316** (real naval, labeled, 554 KB — see `../research/datasets/DATASETS.md`) → register in MLflow → deploy to a Pi → demo a **live update** + a **shore-staged version push** through the bundle. Cleanest "real model on the edge" beat with genuinely naval data.
