#!/usr/bin/env bash
# THESEUS — tear down the emulated UUV fleet (and any background synthetic feeders).
#   bash deploy/pi-emulation/down.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Stop background feeders started by `up.sh --feed`.
if [ -f "$HERE/.feed.pids" ]; then
  while read -r pid; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done < "$HERE/.feed.pids"
  rm -f "$HERE/.feed.pids"
  echo "  · stopped synthetic feeders"
fi
# Belt-and-suspenders: kill any stray local streamers aimed at the emulated nodes.
pkill -f "gen_synthetic_sensors.py --stream --interval .* --url http://127.0.0.1:543" 2>/dev/null || true

docker compose -f "$HERE/docker-compose.yml" down
echo "  ✓ fleet down (MLflow :5050 left running — stop with: bash deploy/mlflow/run.sh stop)"
