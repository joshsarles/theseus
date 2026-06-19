#!/usr/bin/env bash
# THESEUS — bring up the containerized STRIKE GROUP on this Mac, one command.
# (Complements deploy/demo_up.sh, which repopulates the tamper-evident records + flywheel.
#  This one stands up the live edge fleet: MLflow + onboard models + the destroyer containers.)
#
#   bash deploy/strike_group_up.sh          # MLflow + models + 3 destroyers (18 containers)
#                                           # + 2 UUV nodes + the API, all live-fed.
#   bash deploy/strike_group_up.sh --fast   # skip model (re)registration if already @production
#
# Tear it down with: bash deploy/strike_group_down.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PY312="$REPO/deploy/mlflow/.venv312/bin/python"
MLFLOW="http://localhost:5050"
FAST=0; for a in "$@"; do [ "$a" = "--fast" ] && FAST=1; done

say() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

# 1. Shore fleet brain — MLflow registry on :5050.
say "1/6  Node-3 MLflow (shore fleet brain) :5050"
curl -fsS "$MLFLOW/health" >/dev/null 2>&1 || bash "$REPO/deploy/mlflow/run.sh" >/dev/null 2>&1 || true
curl -fsS "$MLFLOW/health" >/dev/null 2>&1 && echo "  ✓ up" || { echo "  ✗ MLflow failed — see deploy/mlflow/mlflow.log"; exit 1; }

# 2. Subsystem + AE models registered @production (skip if already there).
have_model() { curl -fsS "$MLFLOW/api/2.0/mlflow/registered-models/get?name=$1" 2>/dev/null | grep -q '"production"'; }
say "2/6  Onboard models @production"
if [ "$FAST" = 0 ] && ! have_model machinery_deploy; then
  echo "  · registering 6 subsystem models (cbm/cmapss/metropt + uuv c2/nav/sonar)…"
  MLFLOW_TRACKING_URI="$MLFLOW" "$PY312" "$REPO/models/subsystems/train_subsystems.py" >/dev/null 2>&1 || echo "  ⚠ subsystem registration had issues"
fi
if [ "$FAST" = 0 ] && ! have_model theseus-uuv; then
  echo "  · registering theseus-uuv autoencoder…"
  MLFLOW_TRACKING_URI="$MLFLOW" "$PY312" "$REPO/models/uuv/register_uuv_ae.py" >/dev/null 2>&1 || echo "  ⚠ AE registration skipped"
fi
for m in machinery_deploy propulsion_deploy auxiliary_deploy sonar_deploy c2_deploy nav_deploy uuv1_anomaly_deploy uuv2_anomaly_deploy theseus-uuv; do
  have_model "$m" && echo "  ✓ $m" || echo "  ⚠ $m missing"
done

# 3. The two UUV Pi-emulation nodes (sonar + contacts), live-fed.
say "3/6  UUV edge nodes (pi-emulation) :54321/:54322"
bash "$REPO/deploy/pi-emulation/up.sh" --feed --interval=3 2>&1 | sed 's/^/  /' | tail -4

# 4. The destroyer strike group — 3 hulls, 6 subsystem containers each (18 total), live-fed.
say "4/6  Destroyer strike group (DDG-118/119/120, 18 containers)"
bash "$REPO/deploy/ship-emulation/up.sh" --fleet --feed --interval=2 2>&1 | sed 's/^/  /' | tail -14

# 4b. Seal a clean fleet-learning baseline so /api/fleet + /api/oscal serve a verifying record
#     from boot, and the live poison-rejection beat (POST /api/fleet/inject) starts warm
#     (keys + ship deltas primed). Without this the OSCAL panel + inject open cold.
say "4b/6  Fleet brain baseline (fleet record + primed deltas)"
bash "$REPO/fleet/run_miniature.sh" >/dev/null 2>&1 \
  && echo "  ✓ fleet record sealed + verifies (poison-inject beat warm)" \
  || echo "  ⚠ fleet baseline had issues — inject self-primes on first press"

# 5. The demo API on :8501 (serves /api/destroyer, /api/state, /api/mlflow, /api/fleet, /api/oscal).
say "5/6  Demo API :8501"
pkill -f "demo/api.py" 2>/dev/null; (lsof -tiTCP:8501 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null) || true; sleep 1
nohup python3 "$REPO/demo/api.py" > "$REPO/demo/.api.log" 2>&1 </dev/null &
sleep 3
curl -fsS http://localhost:8501/api/destroyer >/dev/null 2>&1 && echo "  ✓ /api/destroyer live" || echo "  ⚠ API not answering yet — see demo/.api.log"

# 6. The UI.
say "6/6  Strike-Group UI"
cat <<EOF
  Run the UI in a separate terminal:
      cd $REPO/frontend/ui && npm run dev
  then open  http://localhost:5173  and switch to the "STRIKE GROUP" scene.

  Live now:
    • MLflow registry  $MLFLOW
    • 3 destroyers, 18 subsystem containers, all streaming  (docker ps)
    • API              http://localhost:8501/api/destroyer
  Down:  bash deploy/strike_group_down.sh
EOF
