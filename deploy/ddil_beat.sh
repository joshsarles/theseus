#!/usr/bin/env bash
# =============================================================================
# THESEUS · DDIL beat — disconnected (cord-pull) model lifecycle + tamper-evidence
# =============================================================================
# WHAT THIS PROVES (one edge node, e.g. a Raspberry Pi at sea):
#   1. The model-delivery loop reaches a known-good state from CACHED operational
#      data (stage -> retrain -> update; model in current; record verifies PASS).
#   2. CORD PULL: with shore unreachable, the loop retrains a fresh version and
#      PROMOTES it from the LOCAL registry — a genuinely NEW version — and the
#      node keeps serving last-good. No shore round-trip.
#   3. BAD UPDATE: a bad new model version is injected and promoted; the node
#      ROLLS BACK locally to the previous good model with NO shore round-trip.
#   4. TAMPER: one leaf in the tamper-evident record is altered; offline verify
#      SNAPS red and names the bad leaf; restore -> verify PASS again.
#
# AIR-GAP / OFFLINE BY DESIGN (this is the demo-fallback hardening):
#   - The CACHED demo/data/staged.csv (real UCI #316 naval gas-turbine CBM data,
#     stated as such) is the AUTHORITATIVE data source. There is NO live network
#     fetch on the critical path. The live UCI #316 download is intentionally
#     DISABLED for this beat so it runs with the internet physically OFF and can
#     never hang or abort under `set -euo pipefail`.
#   - The disable is enforced three ways, in a usercustomize.py loaded into EVERY
#     python subprocess via PYTHONPATH:
#       (a) `ucimlrepo` is made un-importable, so stage_data.py's _fetch_real()
#           returns None immediately and falls to the cached-CSV path; and
#       (b) socket.connect/connect_ex are hard-blocked to FAIL FAST (never hang)
#           — so any accidental outbound call dies instantly instead of stalling
#           the beat; and
#       (c) socket.getaddrinfo (DNS) is hard-blocked for non-local hosts. With the
#           internet physically OFF the resolver itself can hang for many seconds
#           BEFORE connect() is ever reached — that is the real `set -euo pipefail`
#           hang point, so we close it: name resolution for a non-loopback host
#           fails instantly. The cached real UCI #316 staged.csv needs no DNS.
#     A self-check beat proves all three guards are live before the loop runs.
#
# WHAT THIS IS *NOT* (no overclaim):
#   - This is a SINGLE-NODE demonstration of disconnected model lifecycle and
#     tamper-EVIDENCE. It is NOT a multi-node / multi-Pi cluster failover, NOT
#     leader election, NOT Velero/UDS HA. Cluster failover is a separate beat.
#   - The offline guard is a userspace socket block + a disabled fetch path. It
#     proves the loop never NEEDS shore to stage (from cache), promote, serve,
#     roll back, or verify. It is NOT a kernel firewall / airgap proof — for the
#     strongest proof, toggle wifi physically OFF and re-run; the beat behaves
#     identically (see VERIFY note at the bottom).
#   - Tamper-EVIDENT, not tamper-proof. The record proves alteration is DETECTED;
#     it does not prevent a privileged actor from rewriting the whole chain.
#
# RAILS honored: decision-support (no autonomous ship control) · unclassified
# SWAN-side data only · integrate-not-replace · real data stated as such
# (UCI #316 naval gas-turbine CBM) · "deployable; ATO is the gate" not "fielded".
#
# RUN:  bash deploy/ddil_beat.sh                 (needs only python3 + the repo loop)
#       bash deploy/ddil_beat.sh --record /tmp/x (use a specific isolated record dir)
#       bash deploy/ddil_beat.sh --keep          (don't delete the workdir on exit)
#
# SAFE: this beat runs ENTIRELY inside an isolated, throwaway workdir. It NEVER
#       reads or writes the live demo state (demo/out, demo/models, demo/registry)
#       — the running :8501 dashboard's record is untouched by construction. The
#       only thing it reads from the repo is the cached demo/data/staged.csv (copy)
#       and the unmodified referee/chain.py (symlinked). The workdir is removed on
#       exit (success, failure, or Ctrl-C) unless --keep is given.
# =============================================================================
set -euo pipefail

# --- locate repo (script lives in deploy/) -----------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DEMO="$REPO/demo"
PY="${PYTHON:-python3}"

[ -d "$SRC_DEMO" ] || { echo "FATAL: demo/ not found at $SRC_DEMO" >&2; exit 1; }
command -v "$PY" >/dev/null 2>&1 || { echo "FATAL: python3 not found" >&2; exit 1; }
[ -f "$SRC_DEMO/data/staged.csv" ] || {
  echo "FATAL: cached demo/data/staged.csv not found — this beat is offline-by-design" >&2
  echo "       and treats the cached real UCI #316 data as authoritative. Stage it once" >&2
  echo "       online first ( cd demo && python3 stage_data.py )." >&2
  exit 1
}

# --- args --------------------------------------------------------------------
RECORD_OVERRIDE=""   # if set, the isolated record dir is placed here
KEEP_WORK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --record) RECORD_OVERRIDE="${2:-}"; shift 2 ;;
    --keep)   KEEP_WORK=1; shift ;;
    -h|--help)
      sed -n '2,60p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# --- pretty helpers ----------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; GRN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; RST=$'\033[0m'
hr(){ printf '%s\n' "------------------------------------------------------------"; }
beat(){ printf '\n%s== %s ==%s\n' "$BOLD" "$1" "$RST"; }
ok(){   printf '%s  PASS%s  %s\n' "$GRN" "$RST" "$1"; }
bad(){  printf '%s  FAIL%s  %s\n' "$RED" "$RST" "$1"; }
note(){ printf '%s  %s%s\n' "$DIM" "$1" "$RST"; }
die(){  bad "$1"; exit 1; }

# =============================================================================
# ISOLATED WORKDIR — the live demo state is NEVER touched
# =============================================================================
# Layout:
#   $WORK/demo/{stage_data,retrain,update_model,_record}.py   (copies of the loop)
#   $WORK/demo/data/staged.csv   (copy of the authoritative cached real data)
#   $WORK/demo/out/record/       (isolated tamper-evident record == --record dir)
#   $WORK/demo/models/, $WORK/demo/registry/   (isolated model state)
#   $WORK/referee -> $REPO/referee               (unmodified primitives, reused)
#   $WORK/_guard/usercustomize.py                (offline guard for all subprocs)
WORK="$(mktemp -d "${TMPDIR:-/tmp}/theseus_ddil.XXXXXX")"
cleanup(){
  set +e
  if [ "$KEEP_WORK" = "1" ]; then
    note "workdir kept at: $WORK"
  else
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT INT TERM

DEMO="$WORK/demo"
mkdir -p "$DEMO/data"
cp "$SRC_DEMO/stage_data.py" "$SRC_DEMO/retrain.py" \
   "$SRC_DEMO/update_model.py" "$SRC_DEMO/_record.py" "$DEMO/"
cp "$SRC_DEMO/data/staged.csv" "$DEMO/data/staged.csv"
if [ -f "$SRC_DEMO/data/.target" ]; then
  cp "$SRC_DEMO/data/.target" "$DEMO/data/.target"
else
  printf 'gt_compressor_decay' > "$DEMO/data/.target"
fi
ln -s "$REPO/referee" "$WORK/referee"     # reuse the REAL chain.py, unmodified

# isolated record dir (honors --record); models + registry stay inside the demo copy
if [ -n "$RECORD_OVERRIDE" ]; then
  RECORD="$RECORD_OVERRIDE"
  mkdir -p "$RECORD"
  # _record.py / the loop write to demo/out/record; point that at the override
  mkdir -p "$DEMO/out"
  ln -s "$RECORD" "$DEMO/out/record"
else
  RECORD="$DEMO/out/record"
fi
MODELS="$DEMO/models"
REGISTRY="$DEMO/registry/theseus-cbm"

# =============================================================================
# OFFLINE GUARD — make the cached staged.csv authoritative; kill the network path
# =============================================================================
# usercustomize.py runs at interpreter startup in EVERY python subprocess that
# inherits PYTHONPATH (it runs IN ADDITION to the system sitecustomize, so the
# normal site-packages — e.g. scikit-learn — still load). It (a) blocks the
# ucimlrepo import so stage_data.py falls to the cached CSV, and (b) makes any
# outbound socket connect fail INSTANTLY so nothing can ever hang the beat.
mkdir -p "$WORK/_guard"
cat > "$WORK/_guard/usercustomize.py" <<'PY'
import socket as _socket
import sys as _sys

# (a) The cached real UCI #316 staged.csv is authoritative. Disable the live
#     fetch path: make ucimlrepo un-importable so stage_data._fetch_real()->None
#     and the cached-CSV branch is taken with no network attempt.
_sys.modules["ucimlrepo"] = None  # import ucimlrepo -> ImportError (by design)

# (b) Hard fail-fast on ANY outbound connection so an accidental call can never
#     hang under set -euo pipefail. Loopback is left alone so local tooling that
#     legitimately uses 127.0.0.1 (none on this beat) would still function.
_real_connect = _socket.socket.connect
_real_connect_ex = _socket.socket.connect_ex
_real_getaddrinfo = _socket.getaddrinfo

_LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost", "", None)


def _is_local(addr):
    try:
        host = addr[0]
    except Exception:
        return False
    return host in _LOCAL_HOSTS


def _blocked_connect(self, addr, *a, **k):
    if _is_local(addr):
        return _real_connect(self, addr, *a, **k)
    raise OSError(
        "THESEUS DDIL beat: network disabled by design — cached staged.csv is "
        "authoritative (no live UCI #316 fetch). Blocked connect to %r." % (addr,)
    )


def _blocked_connect_ex(self, addr, *a, **k):
    if _is_local(addr):
        return _real_connect_ex(self, addr, *a, **k)
    return 111  # ECONNREFUSED — fail fast, never hang


# (c) Block DNS for non-local hosts. With the internet physically OFF the system
#     resolver can hang for SECONDS before connect() is even reached — the true
#     hang point under set -euo pipefail. Resolving a non-loopback name therefore
#     fails INSTANTLY (gaierror) instead of waiting on a dead resolver. Loopback
#     names still resolve so any local tooling keeps working.
def _blocked_getaddrinfo(host, *a, **k):
    if host in _LOCAL_HOSTS:
        return _real_getaddrinfo(host, *a, **k)
    raise _socket.gaierror(
        _socket.EAI_FAIL,
        "THESEUS DDIL beat: DNS disabled by design — cached staged.csv is "
        "authoritative (no live UCI #316 fetch). Blocked getaddrinfo(%r)." % (host,),
    )


_socket.socket.connect = _blocked_connect
_socket.socket.connect_ex = _blocked_connect_ex
_socket.getaddrinfo = _blocked_getaddrinfo

# Marker so the beat can prove the guard actually loaded.
import os as _os
_marker = _os.environ.get("THESEUS_GUARD_MARKER")
if _marker:
    try:
        open(_marker, "w").write("guard-active")
    except Exception:
        pass
PY

export PYTHONPATH="$WORK/_guard${PYTHONPATH:+:$PYTHONPATH}"
# Belt-and-suspenders: user site MUST be enabled for usercustomize to load.
unset PYTHONNOUSERSITE 2>/dev/null || true

clear 2>/dev/null || true
printf '%s' "$BOLD"
cat <<'BANNER'
 THESEUS · DDIL beat   [ DDIL / AIR-GAP — offline by design ]
 disconnected model lifecycle + tamper-evidence on ONE edge node
BANNER
printf '%s' "$RST"
note "repo:     $REPO"
note "workdir:  $WORK   (isolated; live demo state untouched)"
note "record:   $RECORD"
note "python:   $($PY --version 2>&1)"
hr

# --- offline record verify (returns 0 PASS / 1 SNAP), prints the message ------
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
# GUARD CHECK — prove the offline guard is live BEFORE the loop runs
# =============================================================================
beat "GUARD  Offline-by-design self-check (no network, cached data authoritative)"
GUARD_MARKER="$WORK/.guard_marker"
THESEUS_GUARD_MARKER="$GUARD_MARKER" "$PY" - <<'PY' || die "offline guard self-check FAILED"
import sys, socket, time
# 1) ucimlrepo must be un-importable (live fetch path disabled)
try:
    import ucimlrepo  # noqa: F401
    print("  guard FAIL: ucimlrepo is importable — live fetch path is NOT disabled")
    sys.exit(1)
except ImportError:
    pass
# 2) DNS for a non-local host must fail INSTANTLY (the real hang point when the
#    internet is physically off — the resolver blocks before connect is reached).
t = time.time()
try:
    socket.getaddrinfo("archive.ics.uci.edu", 443)  # UCI host — must be blocked instantly
    print("  guard FAIL: DNS resolved — getaddrinfo is NOT blocked (can hang offline)")
    sys.exit(1)
except socket.gaierror:
    if time.time() - t > 1.0:
        print("  guard FAIL: DNS block was slow — would risk a hang under pipefail")
        sys.exit(1)
# 3) outbound connect must fail fast (never hang) — belt-and-suspenders below DNS
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(("93.184.216.34", 80))  # raw IP (no DNS) — must be blocked instantly
    print("  guard FAIL: outbound connect succeeded — network is NOT blocked")
    sys.exit(1)
except OSError:
    pass
finally:
    s.close()
print("ok")
PY
[ -f "$GUARD_MARKER" ] || die "guard usercustomize did not load (user-site disabled?) — refusing to run"
ok "ucimlrepo import disabled — cached staged.csv is the authoritative source"
ok "DNS (getaddrinfo) blocked for non-local hosts — no resolver hang when offline"
ok "outbound network connect blocked (fail-fast) — beat cannot hang on a fetch"
note "the live UCI #316 download is OFF by design; run with wifi physically off and"
note "this beat behaves identically (the cached real data drives the whole loop)."
hr

# =============================================================================
# STEP 0 — bring the loop to a KNOWN-GOOD state from CACHED data (offline)
# =============================================================================
beat "STEP 0  Known-good state  (stage[cached] -> retrain -> update -> verify)"
note "stage_data.py uses the CACHED real UCI #316 (demo/data/staged.csv), NOT a"
note "live download. retrain + update build and promote the first local version."
STAGE_OUT="$( cd "$DEMO" && "$PY" stage_data.py 2>&1 )" || { printf '%s\n' "$STAGE_OUT"; die "stage_data.py failed"; }
printf '%s\n' "$STAGE_OUT" | sed 's/^/    /'

# AUTHORITATIVE-CACHE assertion: the staged leaf MUST carry source="cache" (the
# cached real UCI #316 CSV), never a live fetch and never the offline PLACEHOLDER.
# Read it straight out of the sealed record so this is verified, not assumed.
STAGE_SRC="$("$PY" - "$RECORD" <<'PY'
import sys, json, base64
from pathlib import Path
rows = [json.loads(l) for l in (Path(sys.argv[1]) / "chain.jsonl").read_text().splitlines() if l.strip()]
src = "none"
for r in rows:                       # last data_staged leaf wins
    if r["kind"] == "data_staged":
        src = json.loads(base64.b64decode(r["record_b64"]))["source"]
print(src)
PY
)"
case "$STAGE_SRC" in
  cache) ok "staged from the CACHED real UCI #316 CSV (sealed source=\"cache\") — authoritative" ;;
  *PLACEHOLDER*) die "stage fell to PLACEHOLDER data (source=\"$STAGE_SRC\") — cached staged.csv was not used" ;;
  *UCI*|*ingest*) die "stage used a non-cache source (source=\"$STAGE_SRC\") — live fetch path was NOT disabled" ;;
  *) die "unexpected staged data source (\"$STAGE_SRC\") — cannot confirm cached data is authoritative" ;;
esac

( cd "$DEMO" && "$PY" retrain.py )      || die "retrain.py failed"
( cd "$DEMO" && "$PY" update_model.py ) || die "update_model.py failed"

GOOD_V="$(current_version)"
[ "$GOOD_V" != "none" ] || die "no model promoted to models/current"
if MSG="$(verify_record)"; then ok "record verifies — $MSG"; else die "record did NOT verify: $MSG"; fi
ok "known-good model = v$GOOD_V serving from models/current (from cached data, offline)"
hr

# =============================================================================
# STEP 1 — CORD PULL: shore unreachable; retrain + promote a genuinely NEW
#          version from the LOCAL registry only
# =============================================================================
beat "STEP 1  Cord pull  (shore unreachable; promote a NEW version, local only)"
note "Already disconnected (network blocked above). Retrain a fresh version and"
note "promote it from the LOCAL registry — the edge-node action, no shore round-trip."
note "This MUST yield a new version number (not a same-version no-op)."

( cd "$DEMO" && "$PY" retrain.py )      || die "retrain.py failed while disconnected"
( cd "$DEMO" && "$PY" update_model.py ) || die "update_model.py failed while disconnected"

DISC_V="$(current_version)"
[ "$DISC_V" != "none" ] || die "no model promoted while disconnected"
# HARD requirement: the cord-pull promote produced a genuinely NEW version.
if [ "$DISC_V" = "$GOOD_V" ]; then
  die "cord-pull promote was a no-op (v$DISC_V == v$GOOD_V) — expected a new version"
fi
ok "promoted a genuinely NEW version: v$GOOD_V -> v$DISC_V (local registry, no shore)"
if MSG="$(verify_record)"; then ok "promoted + verified with NO shore — $MSG"; else die "record did NOT verify offline: $MSG"; fi
ok "edge keeps serving from models/current = v$DISC_V (local registry only)"
note "previous good (v$GOOD_V) kept at models/previous (rollback armed)."
hr

# =============================================================================
# STEP 2 — BAD UPDATE + LOCAL ROLLBACK (still disconnected)
# =============================================================================
beat "STEP 2  Bad model injected -> promote -> detect -> LOCAL rollback"
note "Inject a deliberately-bad version into the LOCAL registry, promote it (so it"
note "becomes 'current' and the good one moves to 'previous'), detect it's bad, and"
note "roll back to models/previous — all with shore still unreachable."

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
( cd "$DEMO" && "$PY" update_model.py ) || die "update_model.py failed promoting bad version"

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
note "rolling back: models/previous -> models/current"
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
    print("FATAL: no models/previous to roll back to", file=sys.stderr); sys.exit(2)
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
[ "$RB_V" = "$DISC_V" ] || note "(rolled back to v$RB_V — the last good before the bad inject)"
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
cp "$RECORD/chain.jsonl" "$WORK/chain.good.jsonl"

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
cp "$WORK/chain.good.jsonl" "$RECORD/chain.jsonl"
if MSG="$(verify_record)"; then ok "restored — record verifies again: $MSG"; else die "restore failed: $MSG"; fi
hr

# =============================================================================
# SUMMARY
# =============================================================================
beat "DDIL beat complete"
ok "G) offline guard ......... ucimlrepo OFF + network blocked (cached data authoritative)"
ok "0) known-good loop ....... built from CACHED real UCI #316, verified PASS"
ok "1) cord pull ............. promoted a genuinely NEW version (v$GOOD_V -> v$DISC_V), no shore"
ok "2) bad update ............ detected + LOCAL rollback, record verifies"
ok "3) tamper ................ SNAPPED red on the exact leaf, restored to PASS"
echo
note "Offline by design: cached demo/data/staged.csv is authoritative; NO live"
note "UCI #316 fetch on the path. Run with wifi physically OFF — identical result."
note "Scope: ONE edge node — disconnected model lifecycle + tamper-evidence."
note "NOT multi-node cluster failover. NOT a kernel-firewall airgap proof."
note "Tamper-EVIDENT, not tamper-proof. Decision-support, human-in-command."
note "Deployable on a Pi; ATO is the gate (not 'fielded')."
echo
note "Ran in an isolated workdir — the live :8501 record was never touched."
# (trap removes the workdir on exit)
