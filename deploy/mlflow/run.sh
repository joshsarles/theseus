#!/usr/bin/env bash
# THESEUS Node-3 MLflow — the fleet model registry + T&E / accreditation-evidence surface.
#
# MLflow 3.x crashes under Python 3.14 (importlib.abc.Traversable was removed; MLflow still
# imports the old path), so it runs in a dedicated Python 3.13 venv. The MLflow *client* still
# imports fine on 3.14, so the fleet/race processes log to it without issue.
#
# Backing store + artifacts are Theseus-owned (under deploy/mlflow/, gitignored runtime).
#   bash deploy/mlflow/run.sh          # launch on :5050 (kills any stale :5050 first)
#   bash deploy/mlflow/run.sh stop     # stop it
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=5050
VENV="$HERE/.venv"

kill_port() {
  local p; p="$(lsof -nP -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$p" ] && { echo "  · killing stale :$PORT ($p)"; kill $p 2>/dev/null || true; sleep 1; kill -9 $p 2>/dev/null || true; } || true
}

[ "${1:-}" = "stop" ] && { kill_port; echo "MLflow stopped."; exit 0; }

# Python 3.13 venv with mlflow (prefer uv; fall back to python3.13 -m venv).
if [ ! -x "$VENV/bin/mlflow" ]; then
  echo "  · creating MLflow venv (Python 3.13)…"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.13 "$VENV" >/dev/null 2>&1
    uv pip install --python "$VENV/bin/python" -q mlflow >/dev/null 2>&1
  else
    python3.13 -m venv "$VENV" && "$VENV/bin/pip" install -q mlflow
  fi
fi

kill_port
# Bind 0.0.0.0 (all interfaces) so the UUV Pis on the LAN can reach Node-3 MLflow, not just
# localhost. Override with MLFLOW_HOST=127.0.0.1 to keep it local-only.
HOST="${MLFLOW_HOST:-0.0.0.0}"
echo "  · launching MLflow on $HOST:$PORT (sqlite backend, artifacts under deploy/mlflow/mlruns)…"
# --serve-artifacts + --artifacts-destination make the server PROXY artifact downloads
# (artifact URIs become mlflow-artifacts:/ instead of a local file:// path), so remote
# clients on the Pis can actually pull registered models. Without this, a remote load fails
# with "No such artifact" because file:// mlruns is only readable on Node 3 itself.
nohup "$VENV/bin/mlflow" server --host "$HOST" --port "$PORT" \
  --backend-store-uri "sqlite:///$HERE/mlflow.db" \
  --serve-artifacts --artifacts-destination "$HERE/mlartifacts" > "$HERE/mlflow.log" 2>&1 &
for _ in $(seq 1 45); do
  curl -fsS -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null && { echo "  ✓ MLflow up → http://127.0.0.1:$PORT"; exit 0; }
  sleep 1
done
echo "  ⚠ MLflow did not come up — see $HERE/mlflow.log"; exit 1
