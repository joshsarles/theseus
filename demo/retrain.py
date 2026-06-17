#!/usr/bin/env python3
"""THESEUS demo — STEP 2: Retrain the model.

Reads the staged data, trains a regressor for the GT compressor decay coefficient,
registers a new versioned model in the local registry, logs to MLflow if a tracking
server is configured (MLFLOW_TRACKING_URI), and seals a `model_trained` leaf.

Degrades gracefully: scikit-learn if present, else a pure-stdlib least-squares
fit so the loop ALWAYS runs (e.g. on a fresh Pi before deps land).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from pathlib import Path

from _record import seal

HERE = Path(__file__).resolve().parent
STAGED = HERE / "data" / "staged.csv"
REGISTRY = HERE / "registry" / "theseus-cbm"
RECORD = HERE / "out" / "record"
TARGET = "gt_compressor_decay"


# Columns that are labels/targets, never features (avoid leakage).
# Secondary label columns to never use as features (leakage). gt_turbine_decay is
# UCI #316's other target; harmless to list for datasets that don't have it.
_EXTRA_DROP = {"gt_turbine_decay"}


def _resolve_target(cli: str | None) -> str:
    """Target column: --target wins, else the .target sidecar stage_data writes
    (= the last CSV column, per the data contract), else the CBM default."""
    if cli:
        return cli
    sidecar = STAGED.parent / ".target"
    if sidecar.exists() and sidecar.read_text().strip():
        return sidecar.read_text().strip()
    return TARGET


def _load_xy(target: str) -> tuple[list[list[float]], list[float], list[str]]:
    import random
    rows = list(csv.DictReader(STAGED.open()))
    if not rows or target not in rows[0]:
        raise SystemExit(f"target '{target}' not in staged data (cols: {list(rows[0])[:8] if rows else []})")
    random.Random(316).shuffle(rows)  # data may be ordered — shuffle for a sane split
    feats: list[str] = []
    for c in rows[0].keys():
        if c == target or c in _EXTRA_DROP:
            continue
        try:
            vals = [float(r[c]) for r in rows]   # numeric-only features
        except ValueError:
            continue                              # skip id/timestamp/string columns
        if len(set(vals)) > 1:                    # drop constants (break OLS)
            feats.append(c)
    X = [[float(r[c]) for c in feats] for r in rows]
    y = [float(r[target]) for r in rows]
    return X, y, feats


def _ols(X: list[list[float]], y: list[float]) -> list[float]:
    """Stdlib multiple linear regression via normal equations (bias prepended)."""
    A = [[1.0, *row] for row in X]
    n, m = len(A), len(A[0])
    # Build (AᵀA) and (Aᵀy)
    ata = [[sum(A[k][i] * A[k][j] for k in range(n)) for j in range(m)] for i in range(m)]
    aty = [sum(A[k][i] * y[k] for k in range(n)) for i in range(m)]
    # Gaussian elimination with partial pivoting
    for i in range(m):
        p = max(range(i, m), key=lambda r: abs(ata[r][i]))
        ata[i], ata[p] = ata[p], ata[i]
        aty[i], aty[p] = aty[p], aty[i]
        piv = ata[i][i] or 1e-12
        for j in range(i, m):
            ata[i][j] /= piv
        aty[i] /= piv
        for r in range(m):
            if r != i and ata[r][i]:
                f = ata[r][i]
                for j in range(i, m):
                    ata[r][j] -= f * ata[i][j]
                aty[r] -= f * aty[i]
    return aty  # [bias, w1, w2, ...]


def _rmse(pred: list[float], y: list[float]) -> float:
    return (sum((p - t) ** 2 for p, t in zip(pred, y)) / len(y)) ** 0.5


def _next_version() -> int:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    vs = [int(p.name[1:]) for p in REGISTRY.glob("v*") if p.name[1:].isdigit()]
    return (max(vs) + 1) if vs else 1


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Retrain + register the model on the staged data.")
    ap.add_argument("--target", help="target column (default: demo/data/.target sidecar = last column, else gt_compressor_decay)")
    a = ap.parse_args()
    target = _resolve_target(a.target)
    print(f"THESEUS demo · STEP 2 — Retrain (target: {target})")
    if not STAGED.exists():
        print("  no staged data — run stage_data.py first")
        return 1
    X, y, feats = _load_xy(target)
    cut = int(len(X) * 0.8)
    Xtr, ytr, Xte, yte = X[:cut], y[:cut], X[cut:], y[cut:]

    framework = "sklearn"
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(random_state=316)
        model.fit(Xtr, ytr)
        pred = list(model.predict(Xte))
        artifact = {"framework": "sklearn", "note": "model pickled alongside"}
        import pickle
        blob = pickle.dumps(model)
    except ImportError:
        framework = "stdlib-ols"
        w = _ols(Xtr, ytr)
        pred = [w[0] + sum(wi * xi for wi, xi in zip(w[1:], row)) for row in Xte]
        artifact = {"framework": "stdlib-ols", "bias": w[0], "weights": dict(zip(feats, w[1:]))}
        blob = json.dumps(artifact, sort_keys=True).encode()

    rmse = _rmse(pred, yte)
    version = _next_version()
    vdir = REGISTRY / f"v{version}"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "model.bin").write_bytes(blob)
    model_sha = hashlib.sha256(blob).hexdigest()
    meta = {
        "name": "theseus-cbm", "version": version, "framework": framework,
        "target": target, "features": feats, "rmse": round(rmse, 6),
        "n_train": len(Xtr), "n_test": len(Xte), "model_sha256": model_sha,
        "trained_unix": time.time(),
    }
    (vdir / "meta.json").write_text(json.dumps(meta, indent=2))

    # MLflow if a server is up (Tommy's central server) — optional, non-fatal.
    if os.environ.get("MLFLOW_TRACKING_URI"):
        try:
            import mlflow
            mlflow.set_experiment(f"theseus-{target}")   # one experiment per dataset/target
            with mlflow.start_run(run_name=f"v{version}"):
                mlflow.log_params({"framework": framework, "n_train": len(Xtr),
                                   "target": target, "n_features": len(feats)})
                mlflow.log_metric("rmse", rmse)
                mlflow.log_artifacts(str(vdir))
            print(f"  logged to MLflow experiment 'theseus-{target}' @ {os.environ['MLFLOW_TRACKING_URI']}")
        except Exception as e:
            print(f"  (MLflow log skipped: {e})")

    seal(RECORD, "model_trained", f"theseus-cbm:v{version}", meta)
    print(f"  framework={framework}  version=v{version}  RMSE={rmse:.5f}")
    print(f"  registered -> {vdir.relative_to(HERE.parent)}  (sha256={model_sha[:12]}…)")
    print("  sealed model_trained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
