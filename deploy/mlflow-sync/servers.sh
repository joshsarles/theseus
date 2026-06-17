#!/usr/bin/env bash
# deploy/mlflow-sync/servers.sh — start/stop/status the SHORE and SHIP MLflow servers.
#
# Usage:
#   ./servers.sh start shore
#   ./servers.sh start ship
#   ./servers.sh stop  shore      # "cut the cable" — proves the ship is disconnected
#   ./servers.sh stop  ship
#   ./servers.sh status
#
# Each server is a real MLflow tracking server (sqlite backend + file artifact
# store) bound to 127.0.0.1 on its own port. Started detached via setsid-style
# nohup so it survives the shell; PID tracked in <dir>/server.pid.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/config.sh"

_wait_ready() {  # $1=uri  — poll /health until 200 or give up (~40s)
  local uri="$1"
  "$VPY" - "$uri" <<'PY'
import sys, time, urllib.request
uri = sys.argv[1].rstrip("/") + "/health"
for _ in range(80):
    try:
        with urllib.request.urlopen(uri, timeout=1) as r:
            if r.status == 200:
                print("ready"); sys.exit(0)
    except Exception:
        pass
    time.sleep(0.5)
print("timeout"); sys.exit(1)
PY
}

_start() {  # $1=name
  local name="$1" dir db arts port pidf log uri
  case "$name" in
    shore) dir="$SHORE_DIR"; db="$SHORE_DB"; arts="$SHORE_ARTIFACTS"; port=$SHORE_PORT; pidf="$SHORE_PIDFILE"; log="$SHORE_LOG"; uri="$SHORE_URI";;
    ship)  dir="$SHIP_DIR";  db="$SHIP_DB";  arts="$SHIP_ARTIFACTS";  port=$SHIP_PORT;  pidf="$SHIP_PIDFILE";  log="$SHIP_LOG";  uri="$SHIP_URI";;
    *) echo "unknown server: $name (want shore|ship)" >&2; exit 2;;
  esac
  mkdir -p "$dir" "$arts"
  if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
    echo "[$name] already running pid=$(cat "$pidf") @ $uri"; return 0
  fi
  echo "[$name] starting MLflow server on :$port (sqlite=$db artifacts=$arts)"
  # nohup + & detaches; setsid not on macOS by default, nohup is enough here.
  nohup "$VBIN/mlflow" server \
      --backend-store-uri "sqlite:///$db" \
      --default-artifact-root "file://$arts" \
      --host 127.0.0.1 --port "$port" \
      >"$log" 2>&1 &
  echo $! > "$pidf"
  if _wait_ready "$uri" >/dev/null; then
    echo "[$name] UP   pid=$(cat "$pidf")  $uri  (health 200)"
  else
    echo "[$name] FAILED to become ready — tail of log:" >&2
    tail -20 "$log" >&2 || true
    exit 1
  fi
}

_stop() {  # $1=name
  local name="$1" pidf uri
  case "$name" in
    shore) pidf="$SHORE_PIDFILE"; uri="$SHORE_URI";;
    ship)  pidf="$SHIP_PIDFILE";  uri="$SHIP_URI";;
    *) echo "unknown server: $name" >&2; exit 2;;
  esac
  if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
    kill "$(cat "$pidf")" 2>/dev/null || true
    # confirm it's actually down (the "cable cut")
    "$VPY" - "$uri" <<'PY'
import sys, time, urllib.request
uri = sys.argv[1].rstrip("/") + "/health"
for _ in range(20):
    try:
        urllib.request.urlopen(uri, timeout=1)
    except Exception:
        print("down"); sys.exit(0)
    time.sleep(0.5)
print("STILL UP"); sys.exit(1)
PY
    rm -f "$pidf"
    echo "[$name] STOPPED ($uri now unreachable)"
  else
    echo "[$name] not running"
    rm -f "$pidf" 2>/dev/null || true
  fi
}

_status() {
  for pair in "shore $SHORE_PIDFILE $SHORE_URI" "ship $SHIP_PIDFILE $SHIP_URI"; do
    set -- $pair; name="$1"; pidf="$2"; uri="$3"
    if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
      echo "[$name] UP   pid=$(cat "$pidf")  $uri"
    else
      echo "[$name] DOWN $uri"
    fi
  done
}

cmd="${1:-}"; arg="${2:-}"
case "$cmd" in
  start) _start "$arg";;
  stop)  _stop  "$arg";;
  status) _status;;
  *) echo "usage: $0 {start|stop} {shore|ship} | status" >&2; exit 2;;
esac
