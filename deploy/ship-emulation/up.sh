#!/usr/bin/env bash
# THESEUS — bring up USS Theseus (DDG-118) as 6 containerized SUBSYSTEM nodes. One command.
#   bash deploy/ship-emulation/up.sh                       # start all 6 subsystems
#   bash deploy/ship-emulation/up.sh --feed                # + synthetic feed into every node (1 rec/30s)
#   bash deploy/ship-emulation/up.sh --feed --interval=2   # livelier feed for a live demo
#   bash deploy/ship-emulation/up.sh --feed --replay       # feed the REALISTIC labeled UUV streams instead of synthetic
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
COMPOSE="$HERE/docker-compose.yml"
FEED=0; INTERVAL=30; REPLAY=0; FLEET=0
for a in "$@"; do case "$a" in
  --feed) FEED=1;;
  --replay) REPLAY=1;;
  --fleet) FLEET=1;;          # also bring up sister hulls DDG-119 + DDG-120 (18 containers total)
  --interval=*) INTERVAL="${a#*=}";;
esac; done

# node -> host-port -> registered model (must match docker-compose.yml + config.*.yml)
NODES=(
  "machinery-node:54541:machinery_deploy"
  "propulsion-node:54542:propulsion_deploy"
  "auxiliary-node:54543:auxiliary_deploy"
  "sonar-node:54544:sonar_deploy"
  "c2-node:54545:c2_deploy"
  "nav-node:54546:nav_deploy"
)

# 1. Image — the byte-identical receiver. Tag the localhost/ variant if needed.
if ! docker image inspect analytics:latest >/dev/null 2>&1; then
  if docker image inspect localhost/analytics:latest >/dev/null 2>&1; then
    docker tag localhost/analytics:latest analytics:latest
    echo "  · tagged localhost/analytics:latest -> analytics:latest"
  else
    echo "  ✗ analytics:latest not found. Get the exact receiver image (Pi must be on):"
    echo "      ssh pi2 'podman save analytics:latest' | docker load && docker tag localhost/analytics:latest analytics:latest"
    echo "    or build from source — see deploy/pi-emulation/README.md"; exit 1
  fi
fi

# 2. Mac-host MLflow on :5050 — the registry every subsystem loads its <key>_deploy model from.
if ! curl -fsS http://localhost:5050/health >/dev/null 2>&1; then
  echo "  · MLflow :5050 down — starting it…"
  bash "$REPO/deploy/mlflow/run.sh" >/dev/null 2>&1 || true
fi
curl -fsS http://localhost:5050/health >/dev/null 2>&1 \
  && echo "  ✓ MLflow :5050 up" \
  || { echo "  ✗ MLflow :5050 failed (see deploy/mlflow/mlflow.log)"; exit 1; }

# 3. Write each subsystem's OWN feature set (mounted into its node so the model scores its
#    real channels, not the default sonar set), then start all 6 nodes.
python3 "$HERE/ship_feed.py" features
docker compose -f "$COMPOSE" up -d --force-recreate

# 4. Wait for each subsystem to load its model + report healthy.
for n in "${NODES[@]}"; do
  name="${n%%:*}"; rest="${n#*:}"; port="${rest%%:*}"; model="${n##*:}"
  printf "  · %-16s (%s) " "$name" "$model"
  for i in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then echo "✓ healthy (:$port)"; break; fi
    printf "."; sleep 1
    [ "$i" = 40 ] && echo " ✗ never became healthy — docker logs $name"
  done
done

# 4b. Optional: bring up the SISTER HULLS (DDG-119 +10, DDG-120 +20) as their own
#     6-container ships, so all three destroyers stream live (the full strike group).
if [ "$FLEET" = 1 ]; then
  for spec in "DDG-119 10" "DDG-120 20"; do
    set -- $spec; hull="$1"; off="$2"; slug="$(echo "$hull" | tr 'A-Z' 'a-z')"
    python3 "$HERE/gen_hull.py" "$hull" "$off" >/dev/null
    docker compose -p "theseus-$slug" -f "$HERE/docker-compose.$slug.yml" up -d >/dev/null 2>&1 \
      && echo "  ✓ $hull up (ports $((54541+off))-$((54546+off)))" \
      || echo "  ✗ $hull failed to start"
  done
fi

# 5. Optional: drive every subsystem with its OWN real data (correct feature set + clearly-
#    labeled synthetic faults on the CSV streams) via ship_feed.py — one threaded process
#    feeding all hulls' nodes (dark ports skipped). (--replay kept for compat.)
if [ "$FEED" = 1 ]; then
  pkill -f "ship_feed.py stream" 2>/dev/null || true
  nohup python3 "$HERE/ship_feed.py" stream --interval "$INTERVAL" > "$HERE/.ship_feed.log" 2>&1 </dev/null &
  echo "$!" > "$HERE/.feed.pids"
  echo "  ✓ feeding all subsystems their own data (1 rec / ${INTERVAL}s) — log: deploy/ship-emulation/.ship_feed.log"
fi

cat <<EOF

USS Theseus (DDG-118) up — 6 subsystems, 1 container each:
  MACHINERY    http://127.0.0.1:54541/health   /history  /stream-item   (machinery_deploy)
  PROPULSION   http://127.0.0.1:54542/health   /history  /stream-item   (propulsion_deploy)
  AUXILIARY    http://127.0.0.1:54543/health   /history  /stream-item   (auxiliary_deploy)
  SONAR        http://127.0.0.1:54544/health   /history  /stream-item   (sonar_deploy)
  C2           http://127.0.0.1:54545/health   /history  /stream-item   (c2_deploy)
  NAV          http://127.0.0.1:54546/health   /history  /stream-item   (nav_deploy)
  MLflow registry  http://127.0.0.1:5050
Feed:  bash deploy/ship-emulation/up.sh --feed [--replay] [--interval=N]
Down:  bash deploy/ship-emulation/down.sh
EOF
