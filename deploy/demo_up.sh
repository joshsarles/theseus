#!/usr/bin/env bash
# THESEUS — one command to bring the demo box to GO.
# Run this any time the live stack is NO-GO (the gitignored demo/out runtime record gets
# wiped by the loop / concurrent processes — preflight will catch it; this fixes it).
#   bash deploy/demo_up.sh
set -uo pipefail
cd "$(dirname "$0")/.."

echo "[demo_up] 1/4 repopulating the one-ship record (stage -> retrain -> update -> AIS PoL)..."
python3 demo/stage_data.py   >/dev/null 2>&1 \
  && python3 demo/retrain.py >/dev/null 2>&1 \
  && python3 demo/update_model.py >/dev/null 2>&1
python3 demo/ais_pol.py --rows 400000 --predictions demo/out/predictions.csv >/dev/null 2>&1
python3 demo/stage_data.py --positions-only >/dev/null 2>&1   # cold-start positions cache

echo "[demo_up] 2/4 regenerating the fleet-learning record (the flywheel)..."
bash fleet/run_miniature.sh >/dev/null 2>&1 || echo "  (fleet miniature warn — non-blocking)"

echo "[demo_up] 3/4 (re)starting the state API on :8501..."
pkill -f "demo/api.py" 2>/dev/null; sleep 0.5
nohup python3 demo/api.py > /tmp/theseus_api.log 2>&1 &
for i in $(seq 1 45); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8501/api/state 2>/dev/null)" = "200" ] && break
  sleep 1
done

echo "[demo_up] 4/4 preflight gate:"
bash deploy/preflight.sh
echo "[demo_up] UI: http://localhost:5173  (if down: cd frontend/ui && npm run preview -- --port 5173 --host)"
echo "[demo_up] Explainer LLM: http://localhost:8080  (if down: llama-server -m <qwen2.5-1.5b gguf> --port 8080)"
