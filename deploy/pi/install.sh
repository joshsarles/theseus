#!/usr/bin/env bash
# THESEUS — one-command edge-node deploy to a Raspberry Pi (arm64, CPU-only, offline).
#
#   ./install.sh '<user>@<host>' <system> [brain-url]
#
# Example:
#   ./install.sh pi@pi1.local machinery http://brain.ship:8077
#   ./install.sh ubuntu@10.0.0.7 contacts
#
# What it does, over SSH (no internet assumed on the Pi):
#   1. rsync/scp the edge runtime onto the Pi:
#        serve/{model_server.py,model_core.py,report_up.py,explain_local.py}
#        referee/                          (the tamper-evident record library)
#        the ONNX model(s) for <system>    (machinery -> CBM, contacts -> autoencoder)
#        a model dir the edge server can serve (machinery: demo/models/current)
#        the on-Pi launcher (edge_run.sh) + systemd unit template
#   2. install a systemd unit (if systemd is present) OR fall back to a nohup launch,
#      starting BOTH the local model server AND report_up (reporting UP to the brain).
#   3. smoke-check the local /health and print status.
#
# PARAMETERIZED on purpose: pi1.local SSH auth (user/key) is operator-owned. Pass the
# real 'user@host'. Re-runnable (idempotent): re-deploying updates files + restarts the
# unit without duplicating anything.
#
# Offline note: Python3 must already be on the Pi. onnxruntime / scikit-learn are
# pre-staged from deploy/pi/wheels/ if present (see README "Pre-stage deps offline").
set -euo pipefail

# ───────────────────────── args ─────────────────────────
TARGET="${1:-}"
SYSTEM="${2:-}"
BRAIN_URL="${3:-http://127.0.0.1:8077}"

usage() {
  echo "usage: $0 '<user>@<host>' <system> [brain-url]" >&2
  echo "  <system>: machinery | contacts | <other> " >&2
  echo "  example: $0 pi@pi1.local machinery http://brain.ship:8077" >&2
  exit 2
}

[ -n "$TARGET" ] || usage
[ -n "$SYSTEM" ] || usage
case "$TARGET" in
  *@*) : ;;
  *) echo "ERROR: target must be 'user@host' (got: $TARGET)" >&2; usage ;;
esac

# Per-system knobs. node-id defaults to <hostpart>-<system>; ports are fixed defaults
# the README documents; override via env if two nodes share a host.
HOSTPART="${TARGET#*@}"
# node-id default: hostname label for *.local names (pi1.local -> pi1), or the full
# host with dots->dashes for bare IPs (10.0.0.7 -> 10-0-0-7) so it stays unique.
case "$HOSTPART" in
  *.local) HOSTKEY="${HOSTPART%%.*}" ;;
  *[0-9].[0-9]*[0-9]) HOSTKEY="$(printf '%s' "$HOSTPART" | tr '.' '-')" ;;
  *) HOSTKEY="${HOSTPART%%.*}" ;;
esac
NODE_ID="${NODE_ID:-${HOSTKEY}-${SYSTEM}}"
EDGE_PORT="${EDGE_PORT:-8080}"
REMOTE_DIR="${REMOTE_DIR:-/opt/theseus-edge}"
SSH_OPTS="${SSH_OPTS:-}"
REPORT_INTERVAL="${REPORT_INTERVAL:-15}"
# STAGE_ONLY=<dir> stages the exact bundle to <dir> and exits BEFORE any SSH — lets an
# operator inspect what would ship (and lets CI verify artifact selection without a Pi).
STAGE_ONLY="${STAGE_ONLY:-}"

# ───────────────────────── locate repo + pick model artifacts ─────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Map the ship system -> the ONNX model file(s) that node serves, and (where it exists)
# a model dir the CBM-style edge server can load+serve.
ONNX_FILES=""
MODEL_DIR_SRC=""
case "$SYSTEM" in
  machinery)
    ONNX_FILES="models/onnx/cbm_regressor.onnx models/onnx/cbm_regressor_int8.onnx models/onnx/infer.py"
    MODEL_DIR_SRC="demo/models/current"
    ;;
  contacts)
    ONNX_FILES="models/onnx/autoencoder.onnx models/onnx/autoencoder_int8.onnx models/onnx/infer.py"
    # AE infer.py reads scaler/threshold from the registry; stage that too.
    ONNX_FILES="$ONNX_FILES demo/registry/theseus-ae"
    MODEL_DIR_SRC="demo/models/current"   # gives the node a servable /health model too
    ;;
  *)
    echo "WARN: unknown system '$SYSTEM' — staging both ONNX models + CBM serve dir." >&2
    ONNX_FILES="models/onnx/cbm_regressor.onnx models/onnx/autoencoder.onnx models/onnx/infer.py demo/registry/theseus-ae"
    MODEL_DIR_SRC="demo/models/current"
    ;;
esac

# Sanity: every source we are about to ship must exist locally.
REQUIRED="serve/model_server.py serve/model_core.py serve/report_up.py serve/explain_local.py referee demo/_record.py $MODEL_DIR_SRC"
for f in $REQUIRED $ONNX_FILES; do
  [ -e "$f" ] || { echo "ERROR: missing local artifact: $f (run from a full THESEUS checkout)" >&2; exit 3; }
done

echo "THESEUS edge deploy"
echo "  target   : $TARGET"
echo "  system   : $SYSTEM   node-id: $NODE_ID"
echo "  brain    : $BRAIN_URL"
echo "  edge port: $EDGE_PORT"
echo "  remote   : $REMOTE_DIR"

# ───────────────────────── stage a flat bundle locally ─────────────────────────
if [ -n "$STAGE_ONLY" ]; then
  STAGE="$STAGE_ONLY"
  rm -rf "$STAGE"   # idempotent: clean slate each stage
  mkdir -p "$STAGE"
else
  STAGE="$(mktemp -d)"
  trap 'rm -rf "$STAGE"' EXIT
fi

mkdir -p "$STAGE/serve" "$STAGE/referee" "$STAGE/demo" "$STAGE/models/onnx" \
         "$STAGE/demo/models/current" "$STAGE/demo/out/record"

cp serve/model_server.py serve/model_core.py serve/report_up.py serve/explain_local.py "$STAGE/serve/"
cp -R referee/. "$STAGE/referee/"
# drop bulky/irrelevant referee bits the edge does not need at runtime
rm -rf "$STAGE/referee/__pycache__"
cp demo/_record.py "$STAGE/demo/"
cp -R "$MODEL_DIR_SRC/." "$STAGE/demo/models/current/"

# ONNX + per-system extras
for f in $ONNX_FILES; do
  case "$f" in
    demo/registry/theseus-ae)
      mkdir -p "$STAGE/demo/registry/theseus-ae"
      cp -R demo/registry/theseus-ae/. "$STAGE/demo/registry/theseus-ae/"
      ;;
    *.py)
      cp "$f" "$STAGE/models/onnx/"
      ;;
    *)
      cp "$f" "$STAGE/models/onnx/"
      ;;
  esac
done

# the on-Pi launcher + unit template + minimal deps manifest
cp "$SCRIPT_DIR/edge_run.sh" "$STAGE/"
cp "$SCRIPT_DIR/theseus-edge.service.tmpl" "$STAGE/"
cp "$SCRIPT_DIR/requirements-pi.txt" "$STAGE/"
[ -d "$SCRIPT_DIR/wheels" ] && cp -R "$SCRIPT_DIR/wheels" "$STAGE/wheels" || true

# Write the node's config so edge_run.sh / systemd know who they are. This is the only
# host-specific file; everything else is identical across nodes.
cat > "$STAGE/node.env" <<EOF
# THESEUS edge node config (generated by install.sh — re-run install.sh to change)
NODE_ID=$NODE_ID
NODE_SYSTEM=$SYSTEM
EDGE_PORT=$EDGE_PORT
EDGE_URL=http://127.0.0.1:$EDGE_PORT
BRAIN_URL=$BRAIN_URL
REPORT_INTERVAL=$REPORT_INTERVAL
REMOTE_DIR=$REMOTE_DIR
MODEL_DIR=$REMOTE_DIR/demo/models/current
RECORD_DIR=$REMOTE_DIR/demo/out/record
EOF

if [ -n "$STAGE_ONLY" ]; then
  echo "  STAGE_ONLY: bundle staged at $STAGE (no SSH performed). Contents:"
  ( cd "$STAGE" && find . -type f | sort | sed 's/^/    /' )
  echo "PASS: dry-run stage complete for system=$SYSTEM node-id=$NODE_ID"
  exit 0
fi

# ───────────────────────── copy to the Pi ─────────────────────────
# Prefer rsync (delta, idempotent); fall back to tar-over-ssh if rsync is absent on
# either side (common on minimal Pi images / offline boxes).
echo "  [1/3] copying bundle -> $TARGET:$REMOTE_DIR"
# SSH_OPTS is an intentional word-split option string; $REMOTE_DIR is meant to expand
# client-side (it is the operator-chosen remote path, not remote-user data).
# shellcheck disable=SC2086,SC2029
ssh $SSH_OPTS "$TARGET" "mkdir -p '$REMOTE_DIR'"
# shellcheck disable=SC2086
if command -v rsync >/dev/null 2>&1 && ssh $SSH_OPTS "$TARGET" "command -v rsync >/dev/null 2>&1"; then
  rsync -az --delete-excluded \
    -e "ssh $SSH_OPTS" \
    "$STAGE/" "$TARGET:$REMOTE_DIR/"
else
  echo "        (rsync unavailable — using tar over ssh)"
  # shellcheck disable=SC2086,SC2029
  tar -C "$STAGE" -czf - . | ssh $SSH_OPTS "$TARGET" "tar -C '$REMOTE_DIR' -xzf -"
fi

# ───────────────────────── install + start on the Pi ─────────────────────────
echo "  [2/3] installing service + starting (serve + report-up)"
# edge_run.sh does the platform decision (systemd vs nohup) on the Pi itself, where it
# can see whether systemd + sudo are available. Idempotent: stops any prior instance.
# $REMOTE_DIR expands client-side by design (operator-chosen path).
# shellcheck disable=SC2086,SC2029
ssh $SSH_OPTS "$TARGET" "cd '$REMOTE_DIR' && chmod +x edge_run.sh && ./edge_run.sh install"

# ───────────────────────── smoke check ─────────────────────────
echo "  [3/3] smoke check (local /health on the Pi)"
sleep 3
# shellcheck disable=SC2086,SC2029
if ssh $SSH_OPTS "$TARGET" "cd '$REMOTE_DIR' && ./edge_run.sh status"; then
  echo
  echo "PASS: edge node '$NODE_ID' (system=$SYSTEM) deployed + serving + reporting up to $BRAIN_URL"
  echo "      verify on the brain:  curl -s $BRAIN_URL/api/state | python3 -m json.tool | grep -A6 '\"$SYSTEM\"'"
else
  echo
  echo "WARN: deployed, but local /health smoke did not confirm. Inspect with:" >&2
  echo "      ssh $TARGET 'cd $REMOTE_DIR && ./edge_run.sh status; ./edge_run.sh logs'" >&2
  exit 1
fi
