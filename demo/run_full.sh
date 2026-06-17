#!/usr/bin/env bash
# THESEUS — the full demo, one command. The live-demo through-line.
#   bash demo/run_full.sh           # run it
#   bash demo/run_full.sh --api     # ...and leave the state API serving for the frontend
#
# Tells the whole story on REAL data, every step sealed in the tamper-evident record:
#   1) MACHINERY  — Stage -> Retrain -> Update (CBM gas-turbine, real UCI #316)
#   2) CONTACTS   — AIS Pattern-of-Life (real MarineCadastre, cold-start, explainable)
#   3) BOARD      — the watchstander view (recommend -> human decides), record verify PASS
# Then: `bash deploy/ddil_beat.sh` for the cord-pull/rollback/tamper beat.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
rule(){ printf "\n\033[1m%s\033[0m\n" "════════════════════════════════════════════════════════════"; }

rule; echo "  THESEUS — onboard ship-systems decision-support (decision-support · human-in-command)"

rule; echo "  1 · MACHINERY / HM&E  — Stage → Retrain → Update (real UCI #316)"
$PY demo/stage_data.py
$PY demo/retrain.py 2>/dev/null | grep -E 'framework|version|RMSE|sealed' || true
$PY demo/update_model.py 2>/dev/null | grep -E 'promoted|previous|sealed|verify' || true

rule; echo "  2 · CONTACTS  — AIS Pattern-of-Life (real MarineCadastre, cold-start)"
if [ -f data/datasets/marinecadastre_us/AIS_2024_01_01.csv ]; then
  $PY demo/ais_pol.py --rows 600000 2>/dev/null | grep -E 'scanned|alerts:|sealed|verify' || true
else
  echo "  (AIS data not present at data/datasets/ — skipping; scp a MarineCadastre slice to enable)"
fi

rule; echo "  3 · WATCHSTANDER BOARD"
$PY demo/show.py

rule; echo "  NEXT: bash deploy/ddil_beat.sh   (cord-pull → local promote → rollback → tamper snaps)"
echo "        the demo is real on real data, every step sealed, runs disconnected."

if [ "${1:-}" = "--api" ]; then
  rule; echo "  Serving the state API for the frontend (Ctrl-C to stop) ..."
  exec $PY demo/api.py
fi
