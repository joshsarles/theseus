#!/usr/bin/env bash
# THESEUS edge — on-Pi launcher. Runs FROM the deployed bundle dir on the Pi itself.
# install.sh copies this over and calls `./edge_run.sh install`. It can also be used
# by hand on the Pi:  ./edge_run.sh {install|start|stop|status|logs|once}
#
# It decides systemd-vs-nohup at runtime (where it can see the Pi), starts BOTH:
#   * the local model server  (serve/model_server.py — /health /version /predict /reload)
#   * the report-up beat       (serve/report_up.py    — reports UP to the brain)
# CPU-only, no GPU, stdlib HTTP server (tiny RAM). Offline-safe: report_up retries.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# load node config (written by install.sh)
# shellcheck disable=SC1091
[ -f node.env ] && . ./node.env

PY="${PY:-python3}"
NODE_ID="${NODE_ID:-edge-node}"
NODE_SYSTEM="${NODE_SYSTEM:-machinery}"
EDGE_PORT="${EDGE_PORT:-8080}"
EDGE_URL="${EDGE_URL:-http://127.0.0.1:$EDGE_PORT}"
BRAIN_URL="${BRAIN_URL:-http://127.0.0.1:8077}"
REPORT_INTERVAL="${REPORT_INTERVAL:-15}"
MODEL_DIR="${MODEL_DIR:-$HERE/demo/models/current}"
RECORD_DIR="${RECORD_DIR:-$HERE/demo/out/record}"
SERVICE_NAME="theseus-edge-${NODE_SYSTEM}"
PID_DIR="$HERE/.run"
mkdir -p "$PID_DIR" "$RECORD_DIR"

have_systemd() { command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; }
can_sudo()     { command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; }

ensure_deps() {
  # Offline-friendly: install from pre-staged wheels/ if present; otherwise just check
  # what's available. The CBM server runs on pure stdlib if the model is stdlib-ols;
  # onnxruntime is only needed for the ONNX infer path.
  if [ -d wheels ] && ls wheels/*.whl >/dev/null 2>&1; then
    echo "  staging python deps from local wheels/ (offline)"
    "$PY" -m pip install --no-index --find-links wheels -r requirements-pi.txt >/dev/null 2>&1 || \
      echo "  (wheel install best-effort; edge server runs on stdlib regardless)"
  fi
}

# ───────────────────────── systemd path ─────────────────────────
install_systemd() {
  local unit="/etc/systemd/system/${SERVICE_NAME}.service"
  echo "  installing systemd unit: $unit"
  # render the template (envsubst-free; plain sed so no extra deps)
  sed -e "s#@HERE@#$HERE#g" \
      -e "s#@PY@#$PY#g" \
      -e "s#@NODE_ID@#$NODE_ID#g" \
      -e "s#@NODE_SYSTEM@#$NODE_SYSTEM#g" \
      -e "s#@EDGE_PORT@#$EDGE_PORT#g" \
      -e "s#@EDGE_URL@#$EDGE_URL#g" \
      -e "s#@BRAIN_URL@#$BRAIN_URL#g" \
      -e "s#@REPORT_INTERVAL@#$REPORT_INTERVAL#g" \
      -e "s#@MODEL_DIR@#$MODEL_DIR#g" \
      -e "s#@RECORD_DIR@#$RECORD_DIR#g" \
      theseus-edge.service.tmpl | sudo tee "$unit" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
  sudo systemctl restart "$SERVICE_NAME"
}

# ───────────────────────── nohup fallback ─────────────────────────
start_nohup() {
  stop_nohup
  echo "  starting (nohup) model_server + report_up"
  # Export so the nohup'd children inherit the config (avoids the line-continued inline
  # prefix scoping pitfall; all values come from node.env / defaults above).
  export EDGE_HOST=0.0.0.0 EDGE_PORT MODEL_DIR RECORD_DIR
  export NODE_ID NODE_SYSTEM BRAIN_URL EDGE_URL REPORT_INTERVAL
  nohup "$PY" serve/model_server.py \
    --port "$EDGE_PORT" --model-dir "$MODEL_DIR" --record-dir "$RECORD_DIR" \
    > "$PID_DIR/model_server.log" 2>&1 &
  echo $! > "$PID_DIR/model_server.pid"
  # give the server a moment to bind before report_up probes it
  sleep 2
  nohup "$PY" serve/report_up.py \
    --brain "$BRAIN_URL" --edge "$EDGE_URL" --node-id "$NODE_ID" --system "$NODE_SYSTEM" \
    --record-dir "$RECORD_DIR" --interval "$REPORT_INTERVAL" \
    > "$PID_DIR/report_up.log" 2>&1 &
  echo $! > "$PID_DIR/report_up.pid"
}

stop_nohup() {
  for svc in model_server report_up; do
    if [ -f "$PID_DIR/$svc.pid" ]; then
      kill "$(cat "$PID_DIR/$svc.pid")" 2>/dev/null || true
      rm -f "$PID_DIR/$svc.pid"
    fi
  done
}

# ───────────────────────── commands ─────────────────────────
cmd_install() {
  ensure_deps
  if have_systemd && can_sudo; then
    install_systemd
  else
    [ "$(id -u)" -eq 0 ] && have_systemd && { install_systemd; return; }
    echo "  systemd/sudo unavailable — using nohup launch"
    start_nohup
  fi
}

cmd_start() { cmd_install; }

cmd_stop() {
  if have_systemd && can_sudo && systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    sudo systemctl stop "$SERVICE_NAME" || true
  fi
  stop_nohup
  echo "  stopped"
}

cmd_status() {
  # local /health is the source of truth — it confirms the model is loaded + serving.
  local out
  if out="$("$PY" - "$EDGE_URL" <<'PY'
import json, sys, urllib.request
url = sys.argv[1].rstrip("/") + "/health"
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        d = json.loads(r.read().decode())
    print("HEALTH ok  v%s (%s) reloads=%s gpu=%s" % (
        d.get("model_version"), d.get("framework"), d.get("reload_count"), d.get("gpu")))
    sys.exit(0)
except Exception as e:
    print("HEALTH FAIL: %s" % e); sys.exit(1)
PY
)"; then
    echo "  $out"
    return 0
  else
    echo "  $out" >&2
    return 1
  fi
}

cmd_logs() {
  if have_systemd && systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
    journalctl -u "$SERVICE_NAME" -n 40 --no-pager 2>/dev/null || true
  fi
  for svc in model_server report_up; do
    [ -f "$PID_DIR/$svc.log" ] && { echo "--- $svc.log (tail) ---"; tail -n 20 "$PID_DIR/$svc.log"; }
  done
}

cmd_once() {
  # one-shot report (no daemon) — handy for a manual hierarchy smoke from the Pi
  "$PY" serve/report_up.py --brain "$BRAIN_URL" --edge "$EDGE_URL" \
    --node-id "$NODE_ID" --system "$NODE_SYSTEM" --record-dir "$RECORD_DIR" --once
}

case "${1:-status}" in
  install) cmd_install ;;
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  logs)    cmd_logs ;;
  once)    cmd_once ;;
  *) echo "usage: $0 {install|start|stop|status|logs|once}" >&2; exit 2 ;;
esac
