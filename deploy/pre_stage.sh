#!/usr/bin/env bash
# =============================================================================
# THESEUS · pre_stage — cache images + verify cluster survival  (Risk #12)
# =============================================================================
# WHAT THIS DOES (the morning-of, before-judges check):
#   The live k3d demo cluster (k3d-theseus) evaporates if the Mac sleeps, and a
#   cold rebuild re-hits the GHCR rate-limit that already stalled the team. This
#   script makes the RUNNING cluster bullet-proof for the demo WITHOUT rebuilding
#   it:
#     1. Pre-pull/cache every demo image LOCALLY (docker) so no live GHCR fetch is
#        needed during the demo.
#     2. Import those images INTO the running k3d-theseus node (`k3d image import`)
#        so kubelet never has to pull from a registry on stage.
#     3. VERIFY the cluster survives intact: the Theseus Job present + Complete,
#        and the Pepr admission controller present + Ready (the live rail).
#     4. Print caffeinate + Docker + ghcr.io-login guidance so it doesn't die
#        overnight or get rate-limited.
#
# WHAT IT DOES *NOT* DO (hard rule — additive/verify only):
#   - It NEVER deletes or recreates k3d-theseus. No `k3d cluster delete/create`,
#     no `kubectl delete`. It only ADDS cached images and READS cluster state.
#   - It does not touch deploy/uds/pepr (Pepr lane) or deploy/ddil_beat.sh.
#   - It does not deploy uds-core into this cluster (see the OPTIONAL section,
#     which is fully isolated and hard-aborts rather than risk the demo cluster).
#
# RUN:   bash deploy/pre_stage.sh                 # cache + verify the live cluster
#        bash deploy/pre_stage.sh --verify-only   # just report health, import nothing
#        CLUSTER=theseus bash deploy/pre_stage.sh
#
# SAFE: additive + read-only w.r.t. the demo. Image import is idempotent. The only
#       state it changes is the image cache on the node (strictly additive).
# =============================================================================
set -uo pipefail   # NOT -e: run every step, report everything; abort only on the few fatal guards.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- config ------------------------------------------------------------------
CLUSTER="${CLUSTER:-theseus}"           # k3d cluster name (context is k3d-$CLUSTER)
CTX="k3d-$CLUSTER"
NS="${NS:-theseus}"                     # the Theseus namespace
JOB="${JOB:-theseus-loop}"              # the in-cluster loop Job
PEPR_NS="${PEPR_NS:-pepr-system}"
VERIFY_ONLY=0
[ "${1:-}" = "--verify-only" ] && VERIFY_ONLY=1

# Images the demo cluster needs cached on-node so kubelet never pulls on stage.
# (Sourced from deploy/uds/manifests/*.yaml + what is already pinned on the node:
#  theseus-edge:0.1.0 [baked loop], pepr controller [the live rail], the k3s
#  system images, and python:3.12-slim [the ConfigMap-over-base Job variant].)
DEMO_IMAGES=(
  "theseus-edge:0.1.0"
  "theseus-serve:0.1.0"
  "ghcr.io/defenseunicorns/pepr/controller:v1.2.1"
  "python:3.12-slim@sha256:9bde4953fa9a7abb6db6669bb1b3f10aac83cf38d69a7bfc4941313ccd4c9686"
)

# --- pretty ------------------------------------------------------------------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; GRN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; DIM=$'\033[2m'; RST=$'\033[0m'
else
  BOLD=''; GRN=''; RED=''; YEL=''; DIM=''; RST=''
fi
FAILS=()
say(){ printf '%s\n' "$*"; }
hr(){  printf '%s\n' "------------------------------------------------------------"; }
beat(){ printf '\n%s== %s ==%s\n' "$BOLD" "$1" "$RST"; }
pass(){ say "${GRN}  PASS${RST}  $1"; }
warn(){ say "${YEL}  WARN${RST}  $1"; }
fail(){ say "${RED}  FAIL${RST}  $1"; FAILS+=("$1"); }
note(){ say "${DIM}  $1${RST}"; }

# --- tool guards (fatal — can't verify a cluster without these) ---------------
command -v docker  >/dev/null 2>&1 || { say "${RED}FATAL: docker not found — start Docker Desktop${RST}"; exit 2; }
command -v kubectl >/dev/null 2>&1 || { say "${RED}FATAL: kubectl not found${RST}"; exit 2; }
command -v k3d     >/dev/null 2>&1 || { say "${RED}FATAL: k3d not found${RST}"; exit 2; }
docker info >/dev/null 2>&1 || { say "${RED}FATAL: Docker daemon not responding — start Docker Desktop and re-run${RST}"; exit 2; }

printf '%s' "$BOLD"
cat <<'BANNER'
 THESEUS · PRE-STAGE
 cache demo images into the live cluster + verify it survives  (Risk #12)
BANNER
printf '%s' "$RST"
note "repo:    $REPO"
note "cluster: $CLUSTER   context: $CTX   namespace: $NS"
hr

# =============================================================================
# GUARD — the cluster must already exist. We add/verify; we NEVER create it here.
# =============================================================================
if ! k3d cluster list 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$CLUSTER"; then
  say "${RED}${BOLD}FATAL: k3d cluster '$CLUSTER' not found.${RST}"
  say "${RED}This script is additive/verify-only by design — it will NOT create or rebuild the demo cluster.${RST}"
  note "If the cluster genuinely needs (re)building, do that deliberately with the team's documented bring-up,"
  note "then re-run this to cache images + verify. Refusing to act blind to avoid destroying live demo state."
  exit 2
fi
pass "k3d cluster '$CLUSTER' exists (not rebuilding — additive only)"

if ! kubectl --context "$CTX" version >/dev/null 2>&1 && ! kubectl --context "$CTX" get ns >/dev/null 2>&1; then
  fail "kubectl cannot reach context '$CTX' — cluster may be stopped. Start it (k3d cluster start $CLUSTER) then re-run."
fi

# =============================================================================
# STEP 1 — PRE-PULL images locally  (so no live registry fetch during the demo)
# =============================================================================
beat "STEP 1  Pre-pull demo images into the LOCAL docker cache"
note "Local-only images (theseus-edge / theseus-serve) are built artifacts — we"
note "verify they exist rather than pulling. Registry images are pulled now so the"
note "demo never hits GHCR live (Risk #12: the rate-limit that already stalled us)."

# Resolve an image reference to one `k3d image import` can actually consume.
# A DIGEST-PINNED ref (repo:tag@sha256:...) is matched by `docker image inspect`
# but k3d's importer looks up the literal repo:tag in the runtime and SKIPS it if
# that tag isn't present (the real failure we caught: python:3.12-slim@sha256
# imported 0 of 1 while the script claimed "imported 4"). Neither a digest ref nor
# a bare image ID is consumable by `k3d image import` on this version — only a
# concrete repo:tag is. Fix: derive repo:tag from the pin (strip @sha256:...) and
# idempotently `docker tag` the pinned image to it, then hand THAT to k3d. The
# content is byte-identical (same digest); the local tag is purely a name k3d
# resolves. Echoes the resolvable ref (or the original if no tagging was needed).
resolve_import_ref() {
  local img="$1" plain
  case "$img" in
    *@sha256:*)
      plain="${img%@sha256:*}"   # repo:tag  (e.g. python:3.12-slim)
      # if it carries no :tag at all (repo@sha256:...), give it a deterministic one
      case "$plain" in */*:* | *:* ) : ;; *) plain="$plain:theseus-pinned" ;; esac
      if docker image inspect "$plain" >/dev/null 2>&1 \
         || docker tag "$img" "$plain" >/dev/null 2>&1; then
        printf '%s' "$plain"
      else
        # last resort: hand back the original (k3d will WARN-skip; Step 2 reports it honestly)
        printf '%s' "$img"
      fi
      ;;
    *) printf '%s' "$img" ;;
  esac
}

LOCAL_OK=()        # original references (for reporting)
LOCAL_OK_REF=()    # k3d-consumable references (parallel array)
for img in "${DEMO_IMAGES[@]}"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    ref="$(resolve_import_ref "$img")"
    if [ "$ref" != "$img" ]; then
      pass "cached: $img  (import as: $ref — digest-pin needs a resolvable ref)"
    else
      pass "cached: $img"
    fi
    LOCAL_OK+=("$img")
    LOCAL_OK_REF+=("$ref")
    continue
  fi
  case "$img" in
    theseus-*)
      # locally-built artifact: do NOT try to pull it from a registry.
      fail "missing local image: $img — build it (deploy/Containerfile / serve/Dockerfile) before demo; not pullable from a registry"
      ;;
    *)
      note "pulling $img ..."
      if docker pull "$img" >/dev/null 2>&1; then
        ref="$(resolve_import_ref "$img")"
        pass "pulled + cached: $img${ref:+  (import as: $ref)}"
        LOCAL_OK+=("$img")
        LOCAL_OK_REF+=("$ref")
      else
        fail "could not pull $img — likely GHCR rate-limit/no-login. Run: docker login ghcr.io   then re-run."
      fi
      ;;
  esac
done

# =============================================================================
# STEP 2 — IMPORT cached images INTO the running cluster node (no on-stage pull)
# =============================================================================
beat "STEP 2  Import cached images into the running cluster ($CTX)"
note "k3d image import copies from docker -> the cluster's containerd. Idempotent;"
note "this does NOT restart or rebuild the cluster — it only seeds the image cache."
if [ "$VERIFY_ONLY" = "1" ]; then
  note "(--verify-only set: skipping import)"
elif [ "${#LOCAL_OK_REF[@]}" -eq 0 ]; then
  fail "no images available locally to import — fix STEP 1 first"
else
  if k3d image import "${LOCAL_OK_REF[@]}" -c "$CLUSTER" >/tmp/theseus_k3d_import.log 2>&1; then
    # k3d can exit 0 yet SKIP an unresolvable ref with a per-image WARN ("is not a
    # file and couldn't be found in the container runtime"). Don't blindly claim N.
    SKIPPED="$(grep -c "couldn't be found in the container runtime" /tmp/theseus_k3d_import.log 2>/dev/null)"
    SKIPPED="${SKIPPED//[!0-9]/}"; SKIPPED="${SKIPPED:-0}"
    if [ "$SKIPPED" -eq 0 ]; then
      pass "imported ${#LOCAL_OK_REF[@]} image(s) into '$CLUSTER' (kubelet will not pull these on stage)"
    else
      warn "k3d exited 0 but SKIPPED $SKIPPED image ref(s) it couldn't resolve — see on-node check below + /tmp/theseus_k3d_import.log"
      grep "couldn't be found" /tmp/theseus_k3d_import.log 2>/dev/null | sed 's/^/      /'
    fi
  else
    fail "k3d image import failed — see /tmp/theseus_k3d_import.log (tail below)"
    tail -8 /tmp/theseus_k3d_import.log 2>/dev/null | sed 's/^/    /'
  fi
fi

# Confirm what containerd on the node actually holds (the truth that matters).
# crictl with -o (default table) shows repo + ID; a digest-pinned image imported by
# ID may appear ONLY under its ID, so we match on the repo name OR the image ID.
NODE_CTR="${CTX}-server-0"
if docker exec "$NODE_CTR" crictl images >/tmp/theseus_node_images.txt 2>/dev/null; then
  # iterate LOCAL_OK (images that were verified+resolved) so indices stay aligned
  # with LOCAL_OK_REF even if some DEMO_IMAGES failed Step 1.
  i=0
  for img in "${LOCAL_OK[@]}"; do
    name="${img%@*}"; name="${name%%:*}"   # strip digest + tag -> bare repo (loose match)
    # the resolved import ref's bare ID (12-char prefix matches crictl's IMAGE ID column)
    ref="${LOCAL_OK_REF[$i]:-}"; i=$((i+1))
    idpfx=""
    case "$ref" in [0-9a-f][0-9a-f][0-9a-f]*) idpfx="${ref:0:12}" ;; esac
    if grep -q "$name" /tmp/theseus_node_images.txt 2>/dev/null \
       || { [ -n "$idpfx" ] && grep -q "$idpfx" /tmp/theseus_node_images.txt 2>/dev/null; }; then
      pass "on-node: $name present in cluster containerd"
    else
      warn "on-node: $name NOT visible in cluster containerd (import may be needed / different ref)"
    fi
  done
else
  warn "could not query on-node images via crictl ($NODE_CTR) — relying on import exit status"
fi

# =============================================================================
# STEP 3 — VERIFY the cluster survived intact  (Job present+Complete, Pepr Ready)
# =============================================================================
beat "STEP 3  Verify cluster survival — Theseus Job + Pepr present"

# 3a) namespace
if kubectl --context "$CTX" get ns "$NS" >/dev/null 2>&1; then
  pass "namespace '$NS' present"
else
  fail "namespace '$NS' MISSING — the Theseus mission app is not deployed in this cluster"
fi

# 3b) the in-cluster loop Job
JOB_JSON="$(kubectl --context "$CTX" -n "$NS" get job "$JOB" -o jsonpath='{.status.succeeded}/{.status.failed}/{.spec.completions}' 2>/dev/null)"
if [ -n "$JOB_JSON" ]; then
  SUCC="${JOB_JSON%%/*}"; rest="${JOB_JSON#*/}"; FAILED="${rest%%/*}"; COMPL="${rest##*/}"
  if [ "${SUCC:-0}" -ge "${COMPL:-1}" ] 2>/dev/null; then
    pass "Job '$JOB' Complete (${SUCC:-0}/${COMPL:-1}) — the loop ran in-cluster (stage->retrain->promote->sealed record)"
  elif [ "${FAILED:-0}" -gt 0 ] 2>/dev/null; then
    fail "Job '$JOB' has ${FAILED} failed pod(s) — the in-cluster loop did not complete cleanly"
  else
    warn "Job '$JOB' present but not yet Complete (succeeded=${SUCC:-0}/${COMPL:-1}) — may still be running"
  fi
else
  fail "Job '$JOB' MISSING in namespace '$NS' — re-apply deploy/uds/manifests/theseus-job*.yaml (do NOT rebuild the cluster)"
fi

# 3c) the Pepr admission controller (the live rail)
PEPR_DEPLOY="$(kubectl --context "$CTX" -n "$PEPR_NS" get deploy -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.readyReplicas}{"/"}{.status.replicas}{"\n"}{end}' 2>/dev/null | grep -i pepr | head -1)"
if [ -n "$PEPR_DEPLOY" ]; then
  PD_NAME="${PEPR_DEPLOY%% *}"; PD_READY="${PEPR_DEPLOY##* }"
  RR="${PD_READY%%/*}"; TR="${PD_READY##*/}"
  if [ -n "$RR" ] && [ "${RR:-0}" -ge 1 ] 2>/dev/null && [ "$RR" = "$TR" ]; then
    pass "Pepr controller Ready ($PD_NAME, $PD_READY) — the human-in-command / hardened-workload rail is LIVE"
  else
    fail "Pepr controller present but NOT Ready ($PD_NAME, ${PD_READY:-?}) — admission rail down; pods would admit unchecked"
  fi
else
  fail "Pepr controller MISSING in '$PEPR_NS' — the live admission rail is not running (the headline UDS/Pepr beat would have no enforcement)"
fi

# 3d) confirm the admission webhook is actually registered (enforcement, not just a pod)
if kubectl --context "$CTX" get validatingwebhookconfigurations 2>/dev/null | grep -qi pepr; then
  pass "Pepr ValidatingWebhookConfiguration registered — admission enforcement is wired to the API server"
else
  warn "no Pepr ValidatingWebhookConfiguration found — controller is up but enforcement may not be wired; verify before the admission beat"
fi

# =============================================================================
# STEP 4 — DON'T-DIE-OVERNIGHT guidance  (caffeinate / Docker / ghcr login)
# =============================================================================
beat "STEP 4  Keep it alive through the night + the demo"

# caffeinate status (advisory — we print the command, we don't background a daemon)
if pgrep -x caffeinate >/dev/null 2>&1; then
  pass "caffeinate already running — Mac will not sleep (cluster survives)"
else
  warn "Mac sleep is NOT inhibited — the cluster will die if it sleeps. Run in a spare terminal and LEAVE IT:"
  note "    caffeinate -dimsu        # display+disk+idle+system; keep this terminal open until after the demo"
fi

# Docker Desktop must keep running (containers are the cluster)
if docker info >/dev/null 2>&1; then
  pass "Docker daemon healthy — keep Docker Desktop running (do NOT quit it)"
fi

# ghcr login — the Risk #12 rate-limit guard. We already cached images, but a
# logged-in daemon is the safety net if anything needs a fresh pull.
if [ -f "$HOME/.docker/config.json" ] && grep -q "ghcr.io" "$HOME/.docker/config.json" 2>/dev/null; then
  pass "docker is logged in to ghcr.io — fresh pulls won't hit the anonymous rate-limit"
else
  warn "NOT logged in to ghcr.io — images are cached so the demo is covered, but log in as a safety net:"
  note "    docker login ghcr.io     # username = GitHub user, password = a PAT with read:packages"
fi

note "Fallback (keep ready regardless): a clean screen-recording of 'kubectl get pods' +"
note "Pepr denying violating pods + cosign verify + tamper-reject, with UDS_DEPLOY_EVIDENCE.md open."

# =============================================================================
# OPTIONAL (time-boxed ~20min, ISOLATED) — uds-core slim-dev in a SEPARATE cluster
# =============================================================================
# HARD RULES for this section:
#   - It NEVER touches k3d-theseus. It would build a DIFFERENT cluster name.
#   - It is HARD-ABORTED unless explicitly opted in (TRY_UDS_CORE=1) AND time-boxed.
#   - If it stalls on a GHCR pull, it aborts and documents — it must not bleed time
#     or rate-limit budget away from the real demo cluster.
# Brief §4 ruling: full uds-core is the highest-cost / lowest-marginal-score item
# and a known-repeat failure. DEFAULT = do not attempt. This block honors that and
# only runs as an explicit, sandboxed, abort-happy experiment.
if [ "${TRY_UDS_CORE:-0}" = "1" ]; then
  beat "OPTIONAL  uds-core slim-dev in an ISOLATED cluster (time-boxed, hard-abort)"
  ISO_CLUSTER="theseus-udscore-iso"
  if [ "$ISO_CLUSTER" = "$CLUSTER" ]; then
    fail "refusing: isolated cluster name collides with the demo cluster — aborting to protect k3d-theseus"
  elif ! command -v uds >/dev/null 2>&1; then
    warn "uds binary not found — skipping isolated uds-core attempt (the demo does NOT depend on this)"
  else
    note "This is a SANDBOX. It will not touch '$CLUSTER'. Hard time-box ~20 min; aborts on any GHCR stall."
    note "Honest status going in: full uds-core (Istio/Keycloak/Operator) was NOT achieved before tonight"
    note "and is CUT from the critical path per the prep brief. This is opportunistic only."
    # need a timeout binary to enforce the hard time-box (macOS has gtimeout via coreutils).
    TIMEOUT_BIN=""
    command -v timeout  >/dev/null 2>&1 && TIMEOUT_BIN="timeout"
    [ -z "$TIMEOUT_BIN" ] && command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN="gtimeout"
    if [ -z "$TIMEOUT_BIN" ]; then
      warn "no timeout/gtimeout found — refusing to run the uds-core sandbox without an enforced time-box (it could bleed the whole session). brew install coreutils to enable."
    elif "$TIMEOUT_BIN" 1200 uds deploy k3d-core-slim-dev --confirm >/tmp/theseus_udscore.log 2>&1; then
      pass "uds-core slim-dev deployed in isolation (bonus) — see /tmp/theseus_udscore.log"
    else
      warn "uds-core slim-dev did NOT complete in the time-box (likely GHCR / Istio image pulls) — ABORTED."
      note "This is the known, documented blocker (Risk #3): full uds-core inheritance is the post-win step,"
      note "blocked by GHCR rate-limit, not a design gap. The demo stands on Pepr + Zarf signed packaging."
      note "log tail:"; tail -6 /tmp/theseus_udscore.log 2>/dev/null | sed 's/^/      /'
    fi
  fi
else
  note ""
  note "OPTIONAL uds-core slim-dev: NOT attempted (default). Per the prep brief §4 it is CUT from the"
  note "critical path (highest cost / lowest marginal score / known GHCR-repeat failure). To try it in a"
  note "fully isolated, time-boxed, abort-happy sandbox that cannot touch k3d-theseus:  TRY_UDS_CORE=1 bash deploy/pre_stage.sh"
fi

# =============================================================================
# VERDICT
# =============================================================================
hr
if [ "${#FAILS[@]}" -eq 0 ]; then
  say "${GRN}${BOLD} CLUSTER HEALTHY  — images cached, Theseus Job + Pepr present. Demo cluster is staged.${RST}"
  say "${DIM}     Keep caffeinate + Docker running. Re-run --verify-only any time to re-confirm.${RST}"
  exit 0
else
  say "${RED}${BOLD} CLUSTER NOT READY  — ${#FAILS[@]} issue(s):${RST}"
  for f in "${FAILS[@]}"; do say "${RED}   ✗ $f${RST}"; done
  say "${DIM}     Fix above (additively — do NOT rebuild the cluster), then re-run.${RST}"
  exit 1
fi
