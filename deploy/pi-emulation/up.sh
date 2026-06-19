#!/usr/bin/env bash
# THESEUS — bring up the emulated 2-Pi UUV fleet on this Mac (Node 3). One command.
#   bash deploy/pi-emulation/up.sh                 # start both nodes
#   bash deploy/pi-emulation/up.sh --feed          # + continuous synthetic feed (1 rec/30s each)
#   bash deploy/pi-emulation/up.sh --feed --interval=2   # livelier feed for a live demo
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
COMPOSE="$HERE/docker-compose.yml"
FEED=0; INTERVAL=30
for a in "$@"; do case "$a" in
  --feed) FEED=1;;
  --interval=*) INTERVAL="${a#*=}";;
esac; done

# 1. Image: prefer the byte-identical image streamed off a Pi; tag it for compose.
if ! docker image inspect analytics:latest >/dev/null 2>&1; then
  if docker image inspect localhost/analytics:latest >/dev/null 2>&1; then
    docker tag localhost/analytics:latest analytics:latest
    echo "  · tagged localhost/analytics:latest -> analytics:latest"
  else
    echo "  ✗ analytics:latest not found. Get the exact Pi image (Pi must be on):"
    echo "      ssh pi2 'podman save analytics:latest' | docker load && docker tag localhost/analytics:latest analytics:latest"
    echo "    or build from source — see deploy/pi-emulation/README.md"; exit 1
  fi
fi

# 2. Node-3 MLflow on :5050 — the registry both nodes load their model from.
if ! curl -fsS http://localhost:5050/health >/dev/null 2>&1; then
  echo "  · MLflow :5050 down — starting it…"
  bash "$REPO/deploy/mlflow/run.sh" >/dev/null 2>&1 || true
fi
curl -fsS http://localhost:5050/health >/dev/null 2>&1 \
  && echo "  ✓ MLflow :5050 up" \
  || { echo "  ✗ MLflow :5050 failed (see deploy/mlflow/mlflow.log)"; exit 1; }

# 3. Start the two emulated Pi nodes.
docker compose -f "$COMPOSE" up -d

# 4. Wait for each to load its model + report healthy.
for n in "uuv1-node:54321" "uuv2-node:54322"; do
  name="${n%%:*}"; port="${n##*:}"; printf "  · %s " "$name"
  for i in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then echo "✓ healthy (:$port)"; break; fi
    printf "."; sleep 1
    [ "$i" = 40 ] && echo " ✗ never became healthy — docker logs $name"
  done
done

# 5. Optional continuous synthetic feed into each node (replaces the Pi-hosted streamer).
if [ "$FEED" = 1 ]; then
  : > "$HERE/.feed.pids"
  for port in 54321 54322; do
    nohup python3 "$REPO/serve/receiver/gen_synthetic_sensors.py" --stream --interval "$INTERVAL" \
      --url "http://127.0.0.1:$port/stream-item" > "$HERE/.feed-$port.log" 2>&1 </dev/null &
    echo $! >> "$HERE/.feed.pids"
  done
  echo "  ✓ feeding both nodes (1 rec / ${INTERVAL}s) — logs: deploy/pi-emulation/.feed-*.log"
fi

cat <<EOF

Fleet up (Node 3 = this Mac):
  UUV-1 (MACHINERY)  http://127.0.0.1:54321/health   /history   /stream-item
  UUV-2 (CONTACTS)   http://127.0.0.1:54322/health   /history   /stream-item
  MLflow registry    http://127.0.0.1:5050
Down:  bash deploy/pi-emulation/down.sh
EOF
