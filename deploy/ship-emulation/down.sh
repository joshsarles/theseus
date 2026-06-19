#!/usr/bin/env bash
# THESEUS — tear down USS Theseus (DDG-118) subsystem fleet (+ any background feeders).
#   bash deploy/ship-emulation/down.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Stop background feeders started by `up.sh --feed`.
if [ -f "$HERE/.feed.pids" ]; then
  while read -r pid; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done < "$HERE/.feed.pids"
  rm -f "$HERE/.feed.pids"
  echo "  · stopped synthetic / replay feeders"
fi
# Belt-and-suspenders: kill any stray local feeders aimed at the subsystem nodes.
pkill -f "ship_feed.py stream" 2>/dev/null || true
pkill -f "gen_synthetic_sensors.py --stream --interval .* --url http://127.0.0.1:5454" 2>/dev/null || true

# Sister hulls (separate compose projects), if they were brought up with --fleet.
for slug in ddg-119 ddg-120; do
  if [ -f "$HERE/docker-compose.$slug.yml" ]; then
    docker compose -p "theseus-$slug" -f "$HERE/docker-compose.$slug.yml" down 2>/dev/null \
      && echo "  · $slug down" || true
  fi
done

docker compose -f "$HERE/docker-compose.yml" down
echo "  ✓ ship(s) down (MLflow :5050 left running — stop with: bash deploy/mlflow/run.sh stop)"
