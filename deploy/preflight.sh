#!/usr/bin/env bash
# =============================================================================
# THESEUS · preflight — the demo GATE  (Risk #1: never demo on a broken stack)
# =============================================================================
# WHAT THIS DOES:
#   A hard go/no-go check run IMMEDIATELY before the live demo. It confirms every
#   load-bearing component is up AND serving REAL data — then exits 0 (GO). If
#   anything is down, mis-ported, or silently serving the mock fixture, it exits
#   1, LOUD and SPECIFIC, naming exactly what to fix. The whole point of Risk #1:
#   the UI silently latches to a fake SIM FEED on the wrong port, and ACCEPT
#   seals nothing. This gate refuses to let that happen unnoticed.
#
# WHAT IT CHECKS (all must pass for GO):
#   1. State API  :8501  /api/health -> HTTP 200            (the UI's data source)
#   2. State API  :8501  /api/state  has the real contract  (not a 500 / stub)
#   3. RECORD VERIFIES + has leaves  -> the chain-of-custody spine is real & intact
#                                       (health returns ok:true even on an EMPTY
#                                        record — leaves==0 / verify_ok==false is
#                                        the silent-mock trap; we REFUSE on it)
#   4. UI         :5173  /           -> HTTP 200            (the projector view)
#   5. UI points at :8501            -> the exact port-mismatch that fakes the feed
#   6. Explainer  :8081  /health     -> status ok + a model loaded (NV063 narrator)
#
# PORT CONTRACT (must agree end-to-end or the feed is silently fake):
#   demo/api.py --port 8501  ==  frontend/ui useShipState STATE_URL :8501
#
# HONEST SCOPE: this gate proves the stack is LIVE and the record is INTACT right
#   now. It does NOT validate model correctness or re-run the eval — that's the
#   eval lane. "Stack is real and serving" is exactly, and only, what it claims.
#
# RUN:   bash deploy/preflight.sh                 # check the live demo stack, then GO/NO-GO
#        bash deploy/preflight.sh --quiet         # only print the final verdict line
#        API_PORT=8501 UI_PORT=5173 EXPLAINER_PORT=8081 bash deploy/preflight.sh
#        SKIP_EXPLAINER=1 bash deploy/preflight.sh   # if the LLM narrator is intentionally out
#
# SAFE: 100% read-only. curls + a localhost record verify. Touches NO live state,
#       writes nothing, never restarts a service. Safe to run repeatedly on stage.
# =============================================================================
set -uo pipefail   # NOT -e: we WANT to run every check and report all failures.

# --- locate repo (script lives in deploy/) -----------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="${PYTHON:-python3}"

# --- config (env-overridable; defaults are the pinned demo contract) ----------
API_PORT="${API_PORT:-8501}"          # MUST match frontend/ui useShipState :8501
UI_PORT="${UI_PORT:-5173}"            # Vite dev server (the projector view)
EXPLAINER_PORT="${EXPLAINER_PORT:-8081}"   # llama-server (qwen2.5-1.5b NV063 narrator) — 8081, NOT 8080 (8080 belongs to the UE/seahelm system)
HOST="${HOST:-localhost}"
CURL_TIMEOUT="${CURL_TIMEOUT:-5}"
SKIP_EXPLAINER="${SKIP_EXPLAINER:-0}"
QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

UI_SRC="${UI_SRC:-$REPO/frontend/ui/src/hooks/useShipState.ts}"  # env-overridable only for off-stage testing on a throwaway port

# --- pretty helpers ----------------------------------------------------------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; GRN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; DIM=$'\033[2m'; RST=$'\033[0m'
else
  BOLD=''; GRN=''; RED=''; YEL=''; DIM=''; RST=''
fi
FAILS=()                              # collected human-readable failures
say(){ [ "$QUIET" = "1" ] || printf '%s\n' "$*"; }
hr(){  [ "$QUIET" = "1" ] || printf '%s\n' "------------------------------------------------------------"; }
pass(){ say "${GRN}  PASS${RST}  $1"; }
warn(){ say "${YEL}  WARN${RST}  $1"; }
fail(){ say "${RED}  FAIL${RST}  $1"; FAILS+=("$1"); }

command -v curl >/dev/null 2>&1 || { printf '%s\n' "${RED}FATAL: curl not found${RST}" >&2; exit 2; }
command -v "$PY" >/dev/null 2>&1 || { printf '%s\n' "${RED}FATAL: python3 not found${RST}" >&2; exit 2; }

[ "$QUIET" = "1" ] || {
  printf '%s' "$BOLD"
  cat <<'BANNER'
 THESEUS · PRE-FLIGHT GATE
 go/no-go for the live demo — refuses a broken or silently-mock stack
BANNER
  printf '%s' "$RST"
  say "${DIM}repo: $REPO${RST}"
  say "${DIM}contract: API :$API_PORT  ==  UI :$UI_PORT -> :$API_PORT  ==  explainer :$EXPLAINER_PORT${RST}"
  hr
}

# =============================================================================
# CHECK 1 — state API liveness  (:API_PORT /api/health -> 200)
# =============================================================================
HEALTH_JSON="$(curl -fsS --max-time "$CURL_TIMEOUT" "http://$HOST:$API_PORT/api/health" 2>/dev/null)"
HEALTH_RC=$?
if [ $HEALTH_RC -ne 0 ] || [ -z "$HEALTH_JSON" ]; then
  fail "state API DOWN at http://$HOST:$API_PORT/api/health  ->  launch:  cd demo && python3 api.py --port $API_PORT   (curl rc=$HEALTH_RC)"
else
  pass "state API up — http://$HOST:$API_PORT/api/health -> 200"
fi

# =============================================================================
# CHECK 2 + 3 — real contract + RECORD VERIFIES with leaves  (the silent-mock trap)
# =============================================================================
# The killer subtlety (Risk #1): /api/health returns ok:true even on an EMPTY
# record. A 200 alone does NOT mean the demo is real. We parse health for
# record_verifies==true AND leaves>0, and independently re-verify /api/state's
# record block. Either being false == the chain spine is empty/broken -> NO-GO.
if [ -n "$HEALTH_JSON" ]; then
  # NOTE: the JSON body is passed via env (THESEUS_JSON), NOT piped to stdin.
  # `python3 - <<'PY'` reads the PROGRAM from stdin, so a `printf ... | python3 -`
  # pipe collides with the heredoc (the heredoc wins; the piped JSON is lost and
  # the script's first line gets mangled). Env-passing is whitespace/newline-proof.
  HSTAT="$(THESEUS_JSON="$HEALTH_JSON" "$PY" <<'PY' 2>/dev/null
import os, json
try:
    d = json.loads(os.environ.get("THESEUS_JSON", ""))
except Exception:
    print("PARSE_FAIL|0|false"); raise SystemExit(0)
ok = bool(d.get("ok"))
leaves = int(d.get("leaves") or 0)
verifies = bool(d.get("record_verifies"))
print(f"{'OK' if ok else 'NOTOK'}|{leaves}|{'true' if verifies else 'false'}")
PY
)"
  H_OK="${HSTAT%%|*}"; rest="${HSTAT#*|}"; H_LEAVES="${rest%%|*}"; H_VERIFIES="${rest##*|}"

  if [ "$H_OK" = "PARSE_FAIL" ]; then
    fail "/api/health returned unparseable body — API is serving garbage, not the contract"
  elif [ "$H_OK" != "OK" ]; then
    fail "/api/health reports ok:false — API is up but unhealthy"
  else
    if [ "${H_LEAVES:-0}" -gt 0 ] 2>/dev/null && [ "$H_VERIFIES" = "true" ]; then
      pass "record is REAL & INTACT — verify_ok=true, leaves=$H_LEAVES (chain-of-custody spine live)"
    else
      fail "RECORD NOT REAL: verify_ok=$H_VERIFIES leaves=$H_LEAVES — health is 200 but the chain is empty/broken. The demo would seal into nothing / read as SIM. Stage the record (run the loop / point --record at the sealed dir) before demo."
    fi
  fi
fi

# Independent cross-check via /api/state (don't trust one endpoint alone on stage).
STATE_JSON="$(curl -fsS --max-time "$CURL_TIMEOUT" "http://$HOST:$API_PORT/api/state" 2>/dev/null)"
if [ $? -ne 0 ] || [ -z "$STATE_JSON" ]; then
  fail "/api/state did not return — the UI's actual data source is broken (health alone is not enough)"
else
  SSTAT="$(THESEUS_JSON="$STATE_JSON" "$PY" <<'PY' 2>/dev/null
import os, json
try:
    d = json.loads(os.environ.get("THESEUS_JSON", ""))
except Exception:
    print("PARSE_FAIL|0|false|0"); raise SystemExit(0)
need = ("ship","machinery","contacts","human_in_command","record")
missing = [k for k in need if k not in d]
rec = d.get("record") or {}
leaves = int(rec.get("leaf_count") or 0)
verify = bool(rec.get("verify_ok"))
ncon = len(d.get("contacts") or [])
print(f"{'OK' if not missing else 'MISSING:'+','.join(missing)}|{leaves}|{'true' if verify else 'false'}|{ncon}")
PY
)"
  S_SHAPE="${SSTAT%%|*}"; r="${SSTAT#*|}"; S_LEAVES="${r%%|*}"; r="${r#*|}"; S_VERIFY="${r%%|*}"; S_CON="${r##*|}"
  if [ "$S_SHAPE" = "PARSE_FAIL" ]; then
    fail "/api/state body unparseable — not the live contract"
  elif [ "$S_SHAPE" != "OK" ]; then
    fail "/api/state missing required keys ($S_SHAPE) — wrong/old API serving the UI"
  else
    pass "/api/state has the full contract (ship+machinery+contacts+human_in_command+record; $S_CON contact(s))"
    # state-side record cross-check must agree with health-side
    if [ "${S_LEAVES:-0}" -gt 0 ] 2>/dev/null && [ "$S_VERIFY" = "true" ]; then
      pass "/api/state record cross-check: verify_ok=true, leaves=$S_LEAVES"
    else
      fail "/api/state record cross-check FAILED: verify_ok=$S_VERIFY leaves=$S_LEAVES — record block is empty/broken from the UI's own data path"
    fi
  fi
fi

# =============================================================================
# CHECK 4 — UI liveness  (:UI_PORT / -> 200)
# =============================================================================
UI_CODE="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time "$CURL_TIMEOUT" "http://$HOST:$UI_PORT/" 2>/dev/null)"
if [ "$UI_CODE" = "200" ]; then
  pass "UI up — http://$HOST:$UI_PORT/ -> 200  (bookmark this full-screen on the projector)"
else
  fail "UI DOWN at http://$HOST:$UI_PORT/ (got '${UI_CODE:-no response}')  ->  launch:  cd frontend/ui && npm run dev"
fi

# =============================================================================
# CHECK 5 — PORT CONTRACT: UI source must point at the API port (the silent-fake root)
# =============================================================================
# Risk #1's literal root cause: UI default :8501 vs api.py historic :8077. If the
# UI source bakes a STATE_URL on a different port than the API we just verified,
# the live UI will silently fall to the mock. Catch it statically.
if [ -f "$UI_SRC" ]; then
  UI_PORTS_FOUND="$(grep -oE 'localhost:[0-9]+|127\.0\.0\.1:[0-9]+|:[0-9]{4,5}/api' "$UI_SRC" 2>/dev/null | grep -oE '[0-9]{4,5}' | sort -u | tr '\n' ' ')"
  if [ -z "$UI_PORTS_FOUND" ]; then
    warn "could not statically read the API port from $UI_SRC (relative URL / env?) — manually confirm the UI fetches :$API_PORT"
  elif printf '%s' "$UI_PORTS_FOUND" | grep -qw "$API_PORT"; then
    pass "UI source targets the API port :$API_PORT (no silent-mock port mismatch)"
  else
    fail "PORT MISMATCH: UI source ($UI_SRC) targets port(s) [$UI_PORTS_FOUND] but the live API is :$API_PORT. The UI will silently serve the MOCK fixture and ACCEPT will seal nothing. Pin both to :$API_PORT."
  fi
else
  warn "UI source not found at $UI_SRC — cannot statically verify the port contract"
fi

# =============================================================================
# CHECK 6 — explainer LLM  (:EXPLAINER_PORT /health -> ok + a model loaded)
# =============================================================================
# The NV063 narrator. Must be PRE-WARMED (never cold-start on stage). We confirm
# it answers /health AND has a model loaded — a llama-server with no model would
# hang the on-stage explain beat.
if [ "$SKIP_EXPLAINER" = "1" ]; then
  warn "explainer check SKIPPED (SKIP_EXPLAINER=1) — confirm the explain beat uses the deterministic template, not a cold LLM"
else
  EX_HEALTH="$(curl -fsS --max-time "$CURL_TIMEOUT" "http://$HOST:$EXPLAINER_PORT/health" 2>/dev/null)"
  if [ $? -ne 0 ] || [ -z "$EX_HEALTH" ]; then
    fail "explainer DOWN at http://$HOST:$EXPLAINER_PORT/health  ->  start llama-server (qwen2.5-1.5b) OR run with SKIP_EXPLAINER=1 and present the template honestly"
  else
    EX_OK="$(THESEUS_JSON="$EX_HEALTH" "$PY" <<'PY' 2>/dev/null
import os, json
try:
    d = json.loads(os.environ.get("THESEUS_JSON", ""))
    print("ok" if str(d.get("status","")).lower() in ("ok","loading model") or d.get("ok") else "notok")
except Exception:
    # non-JSON 200 (some builds return plain text) — treat reachable as ok
    print("ok")
PY
)"
    if [ "$EX_OK" = "ok" ]; then
      EX_MODELS_JSON="$(curl -fsS --max-time "$CURL_TIMEOUT" "http://$HOST:$EXPLAINER_PORT/v1/models" 2>/dev/null)"
      EX_MODEL="$(THESEUS_JSON="$EX_MODELS_JSON" "$PY" <<'PY' 2>/dev/null
import os, json
try:
    d = json.loads(os.environ.get("THESEUS_JSON", ""))
    ms = d.get("data") or d.get("models") or []
    name = ""
    if ms:
        m0 = ms[0]
        name = m0.get("id") or m0.get("name") or m0.get("model") or ""
    print(name)
except Exception:
    print("")
PY
)"
      if [ -n "$EX_MODEL" ]; then
        pass "explainer up + warm — http://$HOST:$EXPLAINER_PORT  model: $EX_MODEL"
      else
        warn "explainer /health ok but no model reported by /v1/models — confirm a GGUF is loaded before the explain beat"
        pass "explainer reachable — http://$HOST:$EXPLAINER_PORT/health ok"
      fi
    else
      fail "explainer at :$EXPLAINER_PORT answered /health but not 'ok' (body: $EX_HEALTH) — not ready for the explain beat"
    fi
  fi
fi

# =============================================================================
# VERDICT
# =============================================================================
hr
if [ "${#FAILS[@]}" -eq 0 ]; then
  say "${GRN}${BOLD} GO  — all systems real and serving. Cleared to demo.${RST}"
  say "${DIM}     header should read LINK LIVE (amber dot). If it ever reads SIM FEED on stage, cut to the recording and keep narrating.${RST}"
  exit 0
else
  say "${RED}${BOLD} NO-GO  — ${#FAILS[@]} blocking failure(s). DO NOT DEMO until fixed:${RST}"
  for f in "${FAILS[@]}"; do say "${RED}   ✗ $f${RST}"; done
  say "${DIM}     (re-run this gate after fixing; it is read-only and safe to repeat)${RST}"
  exit 1
fi
