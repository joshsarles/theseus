#!/usr/bin/env bash
# THESEUS — tear down the containerized strike group (all 3 hulls + UUV nodes + feeders).
# Leaves MLflow :5050 running (stop with: bash deploy/mlflow/run.sh stop).
#   bash deploy/strike_group_down.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

echo "▸ stopping feeders"
pkill -f "ship_feed.py stream" 2>/dev/null || true
pkill -f "gen_synthetic_sensors.py --stream" 2>/dev/null || true

echo "▸ destroyer strike group (3 hulls)"
bash "$REPO/deploy/ship-emulation/down.sh" 2>&1 | sed 's/^/  /' || true

echo "▸ UUV edge nodes"
bash "$REPO/deploy/pi-emulation/down.sh" 2>&1 | sed 's/^/  /' || true

echo "▸ demo API"
pkill -f "demo/api.py" 2>/dev/null || true

echo "✓ strike group down (MLflow :5050 still up — stop with: bash deploy/mlflow/run.sh stop)"
