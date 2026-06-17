# THESEUS child node — model serving (CPU-only, Pi-realistic)

Runs the real Theseus edge inference server (`serve/model_server.py`) on a child
(ship / edge) node. CPU-only, RAM-light — fits a Raspberry Pi 5 (4GB). It serves
the promoted CBM gas-turbine model from `demo/models/current/` and accepts
shore→ship live updates (`POST /reload`), sealing each swap into the
tamper-evident record. **No GPU.**

## What it serves

| Method | Path       | Returns                                                            |
|--------|------------|-------------------------------------------------------------------|
| GET    | `/health`  | `status`, `model_version`, `framework`, `target`, `n_features`, `gpu:false` |
| GET    | `/version` | `version`, `framework`, `target`, `model_sha256`, `features[]`    |
| POST   | `/predict` | body `{"features":{name:value,...}}` → `{"prediction":<float>, ...}` (batch: `{"inputs":[{...}]}`) |
| POST   | `/reload`  | body `{"model_dir":"<path>"}` → hot-swap + seal `edge_model_loaded`; bad model → 422, keeps last-good |

## Run it

From the **repo root** (the build context needs `serve/ demo/ referee/`):

```bash
# 1) point .env at your central MLflow host (optional for serving)
#    edit deploy/child-node-compose/.env -> MLFLOW_SERVER_HOST=<LAN IP>

# 2) bring the edge server up
docker compose -f deploy/child-node-compose/model-serv.yml \
  --env-file deploy/child-node-compose/.env up --build

# 3) verify it
curl http://localhost:8080/health
curl http://localhost:8080/version
```

`/health` should return something like:
```json
{"status":"ok","model_version":1,"framework":"sklearn","target":"gt_compressor_decay","n_features":14,"gpu":false}
```

A real prediction (feature names come from `/version`):
```bash
curl -X POST http://localhost:8080/predict -H 'Content-Type: application/json' \
  -d '{"features":{"lever_position":5.1,"ship_speed":15.0,"gt_shaft_torque":21000,"gt_rpm":2600,"gas_gen_rpm":8200,"stbd_prop_torque":120,"port_prop_torque":120,"hp_turbine_exit_temp":830,"compressor_outlet_temp":680,"hp_turbine_exit_press":2.1,"compressor_outlet_press":11.0,"exhaust_gas_press":1.03,"turbine_injection_ctrl":50.0,"fuel_flow":0.6}}'
```

## Shore → ship live update (no sneakernet)

With the edge server running, the shore side (Tier-1) promotes a new model
version and delivers it; the edge hot-swaps and seals the swap:

```bash
# promote a new version (stage→retrain→update_model) AND deliver it in one shot
python3 serve/deliver.py promote-and-deliver --edge http://localhost:8080

# or in two steps
python3 serve/deliver.py promote
python3 serve/deliver.py deliver --edge http://localhost:8080

# confirm the flip
curl http://localhost:8080/version    # version is now the new one
```

If a delivered model is corrupt/tampered (sha256 mismatch, unpicklable, missing
files), the server **rejects** it (HTTP 422) and keeps serving last-good — DDIL-safe.

## Without Docker (bare Pi)

The server is stdlib + scikit-learn only, so it runs without a container too:

```bash
pip install scikit-learn          # only needed to unpickle sklearn models
python3 serve/model_server.py --port 8080
```

## Run the on-box self-test

Starts a real server, promotes + delivers a new version, verifies the sealed
record, and proves the broken-model rejection — prints PASS/FAIL per check:

```bash
python3 serve/verify_serve.py
```

## Central MLflow server (the other half)

The tracking server lives in `deploy/mlflow-compose/`. Bring it up on the host,
then set `MLFLOW_SERVER_HOST` in `.env` to that host's LAN IP. Serving does **not**
require MLflow — the edge serves fully offline from the promoted model. MLflow is
used by the shore-side retrain step (`demo/retrain.py` logs runs when
`MLFLOW_TRACKING_URI` is set).

### Connectivity troubleshooting
```bash
# from the child node, confirm the tracking server is reachable
curl http://<MLFLOW_SERVER_HOST>:5000/health     # -> {"status":"OK"} from MLflow

# firewall on the MLflow host (ufw / firewalld)
sudo ufw allow 5000/tcp
# or
sudo firewall-cmd --add-port=5000/tcp --permanent && sudo firewall-cmd --reload
```
