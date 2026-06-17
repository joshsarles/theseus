#!/usr/bin/env bash
# THESEUS demo workflow: Stage Operational Data -> Retrain -> Update local model.
# Each step seals into the tamper-evident record; the run ends with an offline verify.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

echo "================ THESEUS model-delivery loop ================"
$PY stage_data.py
echo
$PY retrain.py
echo
$PY update_model.py
echo "============================================================"
echo "Run again to see a NEW version trained, promoted, and the record grow."
echo "Set MLFLOW_TRACKING_URI=http://<server>:5000 to log to the central MLflow."
