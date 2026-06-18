#!/usr/bin/env python3
"""Prove a given MLflow server actually SERVES theseus-cbm: load the registered
model version via pyfunc and run a real prediction on real UCI #316 features.

Used for both sides:
  --side shore : proves the source is real before the gap
  --side ship  : proves the model crossed the gap and the ship can serve it

Usage:
    MLFLOW_TRACKING_URI=<uri> python verify_side.py --side ship \
        --uri http://127.0.0.1:5098 --version 1
Prints a JSON line: {"ok":true,"side":"ship","version":1,"predict_head":[...]}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "demo"))  # reuse demo's data loader (no rewrite)

import mlflow  # noqa: E402
import pandas as pd  # noqa: E402
import retrain as demo_retrain  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["shore", "ship"])
    ap.add_argument("--uri", required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()

    mlflow.set_tracking_uri(args.uri)

    # registry must list the version
    client = mlflow.MlflowClient()
    versions = {int(v.version): v for v in client.search_model_versions("name='theseus-cbm'")}
    if int(args.version) not in versions:
        print(json.dumps({"ok": False, "side": args.side,
                          "error": f"version {args.version} not in registry {sorted(versions)}"}))
        return 1

    # load + predict on real features
    model = mlflow.pyfunc.load_model(f"models:/theseus-cbm/{args.version}")
    target = demo_retrain._resolve_target(None)
    X, y, feats = demo_retrain._load_xy(target)
    df = pd.DataFrame(X[:3], columns=feats)
    pred = [round(float(p), 6) for p in model.predict(df)]

    print(json.dumps({
        "ok": True,
        "side": args.side,
        "uri": args.uri,
        "version": int(args.version),
        "registry_versions": sorted(versions),
        "predict_head": pred,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
