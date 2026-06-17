#!/bin/sh
# THESEUS edge model-delivery loop — step dispatcher (rootless, no-bash, POSIX sh).
#
# The image bakes a READ-ONLY source tree at $THESEUS_SRC (demo/ + referee/ + cot/
# + the pre-staged real UCI #316 staged.csv). On a hardened runtime the root FS is
# read-only (see zarf/manifests/job.yaml: readOnlyRootFilesystem: true), so we copy
# the tree into a WRITABLE work dir ($THESEUS_WORK, default /work — mount an emptyDir
# there) and run from /work/demo. This mirrors the proven referee-smoke Job pattern
# (cp /src -> /work; cd /work; run).
#
# Usage:  <step> [args...]
#   stage_data | retrain | update_model | ais_pol | loop | verify | shell
# Anything else is exec'd verbatim (so `python3 -V`, `sh`, etc. still work).
#
# Rails: decision-support only (human-in-command), SWAN-side/unclassified data,
# integrate-not-replace, tamper-EVIDENT record. Deployable; ATO is the gate.
set -eu

SRC="${THESEUS_SRC:-/opt/theseus}"
WORK="${THESEUS_WORK:-/work}"

seed_work() {
  # Idempotent: only seed once per work volume. Preserves the baked staged.csv.
  if [ ! -d "${WORK}/demo" ]; then
    mkdir -p "${WORK}"
    # -R not -a: do NOT preserve mtime/owner (fails for an arbitrary non-root uid
    # writing into a fresh tmpfs/emptyDir whose root it does not own).
    cp -R "${SRC}/demo" "${SRC}/referee" "${SRC}/cot" "${WORK}/"
  fi
}

run_step() {
  seed_work
  cd "${WORK}/demo"
  # demo scripts do `from _record import seal`; _record.py walks parents[1] -> ${WORK}
  # and imports `referee.chain`, so ${WORK} must hold both demo/ and referee/.
  export PYTHONPATH="${WORK}/demo:${WORK}:${PYTHONPATH:-}"
  exec python3 "$@"
}

step="${1:-loop}"
[ "$#" -gt 0 ] && shift || true

case "${step}" in
  stage_data)   run_step stage_data.py "$@" ;;
  retrain)      run_step retrain.py "$@" ;;
  update_model) run_step update_model.py "$@" ;;
  ais_pol)      run_step ais_pol.py "$@" ;;
  verify)
    # offline record verify — proves the hash-chain without trusting us.
    seed_work
    cd "${WORK}/demo"
    export PYTHONPATH="${WORK}/demo:${WORK}:${PYTHONPATH:-}"
    exec python3 -c "import sys; from _record import verify; ok,_,m=verify(__import__('pathlib').Path('out/record')); print(('PASS ' if ok else 'FAIL ')+m); sys.exit(0 if ok else 2)"
    ;;
  loop)
    # stage -> retrain -> update_model, in sequence (the demo/run.sh story).
    seed_work
    cd "${WORK}/demo"
    export PYTHONPATH="${WORK}/demo:${WORK}:${PYTHONPATH:-}"
    echo "================ THESEUS model-delivery loop ================"
    python3 stage_data.py
    echo
    python3 retrain.py
    echo
    python3 update_model.py
    echo "============================================================"
    ;;
  shell|sh)     exec /bin/sh "$@" ;;
  *)            exec "${step}" "$@" ;;   # passthrough: python3 -V, etc.
esac
