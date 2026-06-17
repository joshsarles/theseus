#!/usr/bin/env bash
# =============================================================================
# THESEUS · DDIL beat — disconnected (cord-pull) model lifecycle + tamper-evidence
# =============================================================================
# WHAT THIS PROVES (one edge node, e.g. a Raspberry Pi at sea):
#   1. The model-delivery loop reaches a known-good state
#      (stage -> retrain -> update; model in demo/models/current; record verifies PASS).
#   2. CORD PULL: with shore unreachable and MLFLOW_TRACKING_URI unset, update_model
#      still PROMOTES from the LOCAL registry and the node keeps serving last-good.
#   3. BAD UPDATE: a bad new model version is injected and promoted; the node
#      ROLLS BACK locally to demo/models/previous with NO shore round-trip.
#   4. TAMPER: one leaf in the tamper-evident record is altered; offline verify
#      SNAPS red and names the bad leaf; restore -> verify PASS again.
#
# WHAT THIS IS *NOT* (no overclaim):
#   - This is a SINGLE-NODE demonstration of disconnected model lifecycle and
#     tamper-EVIDENCE. It is NOT a multi-node / multi-Pi cluster failover, NOT
#     leader election, NOT Velero/UDS HA. Cluster failover is a separate beat.
#   - "Shore blocked" here is simulated in userspace (MLFLOW unset + a dead HTTP
#     proxy so any accidental outbound call fails fast). It is NOT a kernel
#     firewall / airgap proof. The point it makes is real: the loop never needs
#     shore to promote, serve, roll back, or verify.
#   - Tamper-EVIDENT, not tamper-proof. The record proves alteration is DETECTED;
#     it does not prevent a privileged actor from rewriting the whole chain.
#
# RAILS honored: decision-support (no autonomous ship control) · unclassified
# SWAN-side data only · integrate-not-replace · real data stated as such
# (UCI #316 naval gas-turbine CBM) · "deployable; ATO is the gate" not "fielded".
#
# RUN:  bash deploy/ddil_beat.sh          (needs only python3 — stdlib + the repo loop)
# SAFE: non-destructive. It snapshots demo/models and demo/out/record on entry and
#       RESTORES them on exit (success, failure, or Ctrl-C). Your live demo state is
#       returned exactly as it was.
# =============================================================================
set -euo pipefail

# --- locate repo + demo (script lives in deploy/) ----------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
DEMO="$REPO/demo"
PY="${PYTHON:-python3}"

RECORD="$DEMO/out/record"
MODELS="$DEMO/models"
REGISTRY="$DEMO/registry/theseus-cbm"

[ -d "$DEMO" ] || { echo "FATAL: demo/ not found at $DEMO" >&2; exit 1; }
command -v "$PY" >/dev/null 2>&1 || { echo "FATAL: python3 not found" >&2; exit 1; }

# --- pretty helpers ----------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; GRN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; RST=$'\033[0m'
hr(){ printf '%s\n' "------------------------------------------------------------"; }
beat(){ printf '\n%s== %s ==%s\n' "$BOLD" "$1" "$RST"; }
ok(){   printf '%s  PASS%s  %s\n' "$GRN" "$RST" "$1"; }
bad(){  printf '%s  FAIL%s  %s\n' "$RED" "$RST" "$1"; }
note(){ printf '%s  %s%s\n' "$DIM" "$1" "$RST"; }
die(){  bad "$1"; exit 1; }

# --- offline record verify (returns 0 PASS / 1 SNAP), prints the message ------
# REPO is passed as argv (a quoted heredoc cannot expand shell vars inline).
verify_record(){
  "$PY" - "$REPO" "$RECORD" <<'PY'
import sys
from pathlib import Path
repo, record = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
from referee.chain import verify_dir
ok, bad_idx, msg = verify_dir(Path(record))
print(msg + (f"  [bad_leaf={bad_idx}]" if bad_idx is not None else ""))
sys.exit(0 if ok else 1)
PY
}

current_version(){
  "$PY" - "$MODELS/current/meta.json" <<'PY'
import sys, json
try:
    print(json.load(open(sys.argv[1]))["version"])
except Exception:
    print("none")
PY
}

# =============================================================================
# BACKUP / RESTORE — keep the live demo state pristine
# =============================================================================
BACKUP="$(mktemp -d "${TMPDIR:-/tmp}/theseus_ddil.XXXXXX")"
BACKUP_DONE=0   # only restore after a snapshot is fully taken (never wipe on early abort)

# restore() is a SWAP, never a one-way delete: a live dir is only removed when we
# actually hold a backup to put back. If a dir had no backup (it didn't exist at
# start), we LEAVE whatever the run produced rather than deleting regenerated state.
restore(){
  set +e
  [ "$BACKUP_DONE" = "1" ] || { note "no snapshot taken yet — leaving demo state untouched."; rm -rf "$BACKUP"; return; }
  note "restoring live demo state from snapshot ($BACKUP) ..."
  if [ -d "$BACKUP/models" ];   then rm -rf "$MODELS";   cp -R "$BACKUP/models"   "$MODELS";   fi
  if [ -d "$BACKUP/registry" ]; then rm -rf "$REGISTRY"; cp -R "$BACKUP/registry" "$REGISTRY"; fi
  if [ -d "$BACKUP/record" ];   then rm -rf "$RECORD"; mkdir -p "$(dirname "$RECORD")"; cp -R "$BACKUP/record" "$RECORD"; fi
  rm -rf "$BACKUP"
  note "restore complete — your demo is exactly as you left it."
}
trap restore EXIT INT TERM

mkdir -p "$BACKUP"
[ -d "$MODELS" ]   && cp -R "$MODELS"   "$BACKUP/models"
[ -d "$REGISTRY" ] && cp -R "$REGISTRY" "$BACKUP/registry"
[ -d "$RECORD" ]   && cp -R "$RECORD"   "$BACKUP/record"
BACKUP_DONE=1

clear 2>/dev/null || true
printf '%s' "$BOLD"
cat <<'BANNER'
 THESEUS · DDIL beat
 disconnected model lifecycle + tamper-evidence on ONE edge node
BANNER
printf '%s' "$RST"
note "repo:   $REPO"
note "demo:   $DEMO"
note "python: $($PY --version 2>&1)"
hr

# =============================================================================
# STEP 0 — bring the loop to a KNOWN-GOOD state (shore allowed; this is "in port")
# =============================================================================
beat "STEP 0  Known-good state  (stage -> retrain -> update -> verify)"
note "Running the existing repo loop. stage_data caches real UCI #316 (real naval"
note "gas-turbine CBM data, stated as such); offline-safe once cached."
( cd "$DEMO" && "$PY" stage_data.py )   || die "stage_data.py failed"
( cd "$DEMO" && "$PY" retrain.py )      || die "retrain.py failed"
( cd "$DEMO" && "$PY" update_model.py ) || die "update_model.py failed"

GOOD_V="$(current_version)"
[ "$GOOD_V" != "none" ] || die "no model promoted to demo/models/current"
if MSG="$(verify_record)"; then ok "record verifies — $MSG"; else die "record did NOT verify: $MSG"; fi
ok "known-good model = v$GOOD_V serving from demo/models/current"
hr

# =============================================================================
# STEP 1 — CORD PULL: shore unreachable; promote + serve from LOCAL registry only
# =============================================================================
beat "STEP 1  Cord pull  (shore unreachable; MLflow unset)"
note "Simulating disconnection: unset MLFLOW_TRACKING_URI and point all HTTP at a"
note "dead proxy so ANY accidental outbound call fails fast. Then retrain + promote."
note "If the loop reached shore, this step would hang/fail. It must not."

# train a fresh version while 'disconnected'
( cd "$DEMO" \
  && unset MLFLOW_TRACKING_URI \
  && http_proxy="http://127.0.0.1:9"  https_proxy="http://127.0.0.1:9" \
     HTTP_PROXY="http://127.0.0.1:9"  HTTPS_PROXY="http://127.0.0.1:9" \
     no_proxy="" NO_PROXY="" \
     "$PY" retrain.py ) || die "retrain.py failed while disconnected"

# promote it from the LOCAL registry — the edge-node action; no shore round-trip
( cd "$DEMO" \
  && unset MLFLOW_TRACKING_URI \
  && http_proxy="http://127.0.0.1:9"  https_proxy="http://127.0.0.1:9" \
     HTTP_PROXY="http://127.0.0.1:9"  HTTPS_PROXY="http://127.0.0.1:9" \
     "$PY" update_model.py ) || die "update_model.py failed while disconnected"

DISC_V="$(current_version)"
[ "$DISC_V" != "none" ] || die "no model promoted while disconnected"
[ "$DISC_V" != "$GOOD_V" ] || note "(version unchanged — registry had no newer model; promotion still local-only)"
if MSG="$(verify_record)"; then ok "promoted + verified with NO shore — $MSG"; else die "record did NOT verify offline: $MSG"; fi
ok "edge keeps serving from demo/models/current = v$DISC_V (local registry only)"
note "previous good kept at demo/models/previous (rollback armed)."
hr

# =============================================================================
# STEP 2 — BAD UPDATE + LOCAL ROLLBACK (still disconnected)
# =============================================================================
beat "STEP 2  Bad model injected -> promote -> detect -> LOCAL rollback"
note "Inject a deliberately-bad version into the LOCAL registry, promote it (so it"
note "becomes 'current' and the good one moves to 'previous'), detect it's bad, and"
note "roll back to demo/models/previous — all with shore still unreachable."

# 2a) inject a bad version v999 (valid shape, sentinel-bad RMSE) into the registry
BAD_VER=999
"$PY" - "$REGISTRY" "$BAD_VER" <<'PY'
import sys, json, hashlib, time
from pathlib import Path
reg = Path(sys.argv[1]); ver = int(sys.argv[2])
vdir = reg / f"v{ver}"; vdir.mkdir(parents=True, exist_ok=True)
blob = b"BAD-MODEL-DO-NOT-SERVE"          # not a usable model artifact
(vdir / "model.bin").write_bytes(blob)
meta = {
    "name": "theseus-cbm", "version": ver, "framework": "corrupt-inject",
    "target": "gt_compressor_decay", "features": [],
    "rmse": 9.999999,                      # sentinel: absurd error -> obviously bad
    "n_train": 0, "n_test": 0,
    "model_sha256": hashlib.sha256(blob).hexdigest(),
    "trained_unix": time.time(),
    "_demo_injected_bad": True,
}
(vdir / "meta.json").write_text(json.dumps(meta, indent=2))
print(f"injected bad v{ver} (rmse={meta['rmse']}) into local registry")
PY
note "promoting latest (the bad v$BAD_VER) via the normal edge path ..."
( cd "$DEMO" \
  && unset MLFLOW_TRACKING_URI \
  && http_proxy="http://127.0.0.1:9" https_proxy="http://127.0.0.1:9" \
     "$PY" update_model.py ) || die "update_model.py failed promoting bad version"

NOW_V="$(current_version)"
if [ "$NOW_V" = "$BAD_VER" ]; then
  note "current is now v$NOW_V — the BAD model is live (this is the failure we catch)."
else
  die "expected bad v$BAD_VER to be current, got v$NOW_V"
fi

# 2b) GATE: read the served model's own metadata; an RMSE this bad fails the gate.
GATE_BAD="$("$PY" - "$MODELS/current/meta.json" <<'PY'
import sys, json
m = json.load(open(sys.argv[1]))
# Edge acceptance gate: refuse a model whose self-reported RMSE blows the envelope.
THRESH = 0.05
print("BAD" if (m.get("rmse", 9e9) > THRESH or m.get("_demo_injected_bad")) else "OK")
PY
)"
if [ "$GATE_BAD" = "BAD" ]; then
  bad "edge acceptance gate REJECTS current v$NOW_V (RMSE out of envelope) — rolling back"
else
  die "gate failed to flag the bad model"
fi

# 2c) LOCAL rollback: previous -> current (no shore), then seal + offline verify
note "rolling back: demo/models/previous -> demo/models/current"
"$PY" - "$REPO" "$MODELS" "$RECORD" <<'PY'
import sys, json, shutil
from pathlib import Path
repo, models, record = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, repo)
from referee.chain import verify_dir
sys.path.insert(0, str(Path(repo) / "demo"))
from _record import seal

cur, prev = models / "current", models / "previous"
if not prev.exists():
    print("FATAL: no demo/models/previous to roll back to", file=sys.stderr); sys.exit(2)
bad_meta  = json.load(open(cur / "meta.json"))
good_meta = json.load(open(prev / "meta.json"))
shutil.rmtree(cur)
shutil.copytree(prev, cur)
seal(Path(record), "model_rolled_back", f"theseus-cbm:v{good_meta['version']}", {
    "rolled_back_from": bad_meta["version"],
    "restored_version": good_meta["version"],
    "reason": "edge acceptance gate: RMSE out of envelope (disconnected)",
    "restored_model_sha256": good_meta["model_sha256"],
})
ok, _, msg = verify_dir(Path(record))
print(f"restored v{good_meta['version']} -> current; sealed model_rolled_back")
print(f"VERIFY:{'PASS' if ok else 'SNAP'}|{msg}")
sys.exit(0 if ok else 3)
PY
RB_RC=$?
[ $RB_RC -eq 0 ] || die "rollback path failed (rc=$RB_RC)"

RB_V="$(current_version)"
[ "$RB_V" = "$GOOD_V" ] || note "(rolled back to v$RB_V — the last good before the bad inject)"
if MSG="$(verify_record)"; then ok "rolled back to v$RB_V; record still verifies — $MSG"; else die "record broke after rollback: $MSG"; fi
ok "edge recovered to a known-good model with NO shore contact"
hr

# =============================================================================
# STEP 3 — TAMPER DETECTION (offline verify SNAPS red, then restore)
# =============================================================================
beat "STEP 3  Tamper one leaf -> verify SNAPS red -> restore -> verify PASS"
note "Flip one byte inside a single record leaf. Offline verify must DETECT it and"
note "name the broken leaf. Tamper-EVIDENT, not tamper-proof."

# snapshot the good chain so we can restore it precisely
cp "$RECORD/chain.jsonl" "$BACKUP/chain.good.jsonl"

# pick a middle leaf to tamper (exists in every run)
TAMPER_IDX="$("$PY" - "$RECORD/chain.jsonl" <<'PY'
import sys
n = sum(1 for l in open(sys.argv[1]) if l.strip())
print(max(0, n // 2))
PY
)"
note "tampering leaf index $TAMPER_IDX ..."
"$PY" - "$REPO" "$RECORD" "$TAMPER_IDX" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from referee.chain import tamper
print(tamper(Path(sys.argv[2]), int(sys.argv[3])))
PY

# verify MUST now fail (we invert the meaning of the exit code here)
if MSG="$(verify_record)"; then
  die "tamper went UNDETECTED — verify still PASSed: $MSG"
else
  ok "tamper DETECTED — verify snapped red: $MSG"
fi

# restore the good chain and re-verify
note "restoring untampered chain.jsonl ..."
cp "$BACKUP/chain.good.jsonl" "$RECORD/chain.jsonl"
if MSG="$(verify_record)"; then ok "restored — record verifies again: $MSG"; else die "restore failed: $MSG"; fi
hr

# =============================================================================
# SUMMARY
# =============================================================================
beat "DDIL beat complete"
ok "0) known-good loop ........ verified PASS"
ok "1) cord pull ............. promoted + served from LOCAL registry, no shore"
ok "2) bad update ............ detected + LOCAL rollback, record verifies"
ok "3) tamper ................ SNAPPED red on the exact leaf, restored to PASS"
echo
note "Scope: ONE edge node — disconnected model lifecycle + tamper-evidence."
note "NOT multi-node cluster failover. NOT a kernel-firewall airgap proof."
note "Tamper-EVIDENT, not tamper-proof. Decision-support, human-in-command."
note "Deployable on a Pi; ATO is the gate (not 'fielded')."
echo
# (trap restores live demo state on exit)
