# deploy/mlflow-sync/config.sh — shared config for the shore->ship MLflow sync.
# Sourced by every script here. All paths absolute so cwd never matters.
#
# Two LOCAL MLflow servers stand in for two physical machines across a DDIL gap:
#   SHORE = connected enclave (trains + registers the model)
#   SHIP  = disconnected platform (afloat; can't reach shore)
#
# Distinct ports/dirs so we NEVER touch Tommy's MLflow (:5001 docker), the
# loop's demo/registry, or the repo-root default mlflow.db.

# Resolve this dir regardless of how we're sourced.
SYNC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$SYNC_DIR/../.." && pwd)"

VENV="$SYNC_DIR/.venv"
VPY="$VENV/bin/python"
VBIN="$VENV/bin"

# --- SHORE (connected) ---
SHORE_DIR="$SYNC_DIR/shore"
SHORE_DB="$SHORE_DIR/mlflow.db"
SHORE_ARTIFACTS="$SHORE_DIR/artifacts"
SHORE_PORT=5097
SHORE_URI="http://127.0.0.1:${SHORE_PORT}"
SHORE_PIDFILE="$SHORE_DIR/server.pid"
SHORE_LOG="$SHORE_DIR/server.log"

# --- SHIP (disconnected) ---
SHIP_DIR="$SYNC_DIR/ship"
SHIP_DB="$SHIP_DIR/mlflow.db"
SHIP_ARTIFACTS="$SHIP_DIR/artifacts"
SHIP_PORT=5098
SHIP_URI="http://127.0.0.1:${SHIP_PORT}"
SHIP_PIDFILE="$SHIP_DIR/server.pid"
SHIP_LOG="$SHIP_DIR/server.log"

# --- the gap (removable media / cross-domain transfer stand-in) ---
TRANSFER_DIR="$SYNC_DIR/transfer"
BUNDLE_DIR="$TRANSFER_DIR/theseus-cbm-bundle"

# --- model + record ---
MODEL_NAME="theseus-cbm"
RECORD_DIR="$SYNC_DIR/out/record"   # our OWN record dir (not demo/out/record)
