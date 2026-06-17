#!/usr/bin/env python3
"""THESEUS — PyTorch autoencoder anomaly detector (the unsupervised "ship's doctor").

Trains on NORMAL machinery data only, scores per-sample reconstruction error, and flags
high-error samples as anomalies — NO anomaly labels needed at train time (the cold-start /
no-historical-DB story for the engineering organ). Validated against MetroPT-3's REAL
labeled compressor failures (precision/recall/false-alarm). Logs to MLflow, registers the
model, seals to the tamper-evident record. Pairs with Nick's IsolationForest pipeline
(`train.py`) and complements the regression loop (`retrain.py`).

  python3 demo/autoencoder.py [--data ingest/out/metropt.csv] [--epochs 40] [--target-far 0.02]

Rails: decision-support (flags for review, never auto-acts) · real data · tamper-evident.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from pathlib import Path

from _record import seal

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent / "ingest" / "out" / "metropt.csv"
REGISTRY = HERE / "registry" / "theseus-ae"
RECORD = HERE / "out" / "record"
LABEL = "is_anomaly"   # last column = label; used ONLY for eval, never for training


def _load(path: Path):
    rows = list(csv.DictReader(path.open()))
    cols = [c for c in rows[0] if c != LABEL]
    # numeric, non-constant features only
    feats = []
    for c in cols:
        try:
            vals = [float(r[c]) for r in rows]
        except ValueError:
            continue
        if len(set(vals)) > 1:
            feats.append(c)
    X = [[float(r[c]) for c in feats] for r in rows]
    y = [int(float(r.get(LABEL, 0))) for r in rows]
    return X, y, feats


def main() -> int:
    ap = argparse.ArgumentParser(description="Unsupervised autoencoder anomaly detector.")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--target-far", type=float, default=0.02,
                    help="threshold set at this false-alarm rate on normal-validation (default 0.02)")
    a = ap.parse_args()

    import torch
    import torch.nn as nn
    torch.manual_seed(316)

    data = Path(a.data)
    if not data.exists():
        print(f"  data not found: {data} (run `python3 ingest/metropt.py` first)")
        return 1
    print(f"THESEUS · autoencoder anomaly detector  (data: {data.name})")
    X, y, feats = _load(data)
    n, d = len(X), len(feats)

    # standardize using NORMAL rows only (no leakage from anomalies)
    import statistics
    normal_idx = [i for i in range(n) if y[i] == 0]
    mean = [statistics.fmean(X[i][j] for i in normal_idx) for j in range(d)]
    std = [(statistics.pstdev([X[i][j] for i in normal_idx]) or 1.0) for j in range(d)]
    Z = [[(X[i][j] - mean[j]) / std[j] for j in range(d)] for i in range(n)]

    # split: train on 80% of NORMAL; validate threshold on the other 20% normal; test on ALL
    cut = int(len(normal_idx) * 0.8)
    tr_idx, val_idx = normal_idx[:cut], normal_idx[cut:]
    Xtr = torch.tensor([Z[i] for i in tr_idx], dtype=torch.float32)
    Xval = torch.tensor([Z[i] for i in val_idx], dtype=torch.float32)
    Xall = torch.tensor(Z, dtype=torch.float32)

    # small autoencoder: d -> d/2 -> d/4 -> d/2 -> d
    h1, h2 = max(2, d // 2), max(2, d // 4)
    ae = nn.Sequential(
        nn.Linear(d, h1), nn.ReLU(), nn.Linear(h1, h2), nn.ReLU(),
        nn.Linear(h2, h1), nn.ReLU(), nn.Linear(h1, d),
    )
    opt = torch.optim.Adam(ae.parameters(), lr=1e-3)
    lossf = nn.MSELoss()
    for ep in range(a.epochs):
        ae.train(); opt.zero_grad()
        loss = lossf(ae(Xtr), Xtr)
        loss.backward(); opt.step()
        if ep % 10 == 0 or ep == a.epochs - 1:
            print(f"  epoch {ep:3d}  train_recon_mse={loss.item():.5f}")

    ae.eval()
    with torch.no_grad():
        err_val = ((ae(Xval) - Xval) ** 2).mean(dim=1).tolist()
        err_all = ((ae(Xall) - Xall) ** 2).mean(dim=1).tolist()

    # threshold = the (1 - target_far) quantile of NORMAL-validation recon error
    err_val_sorted = sorted(err_val)
    q = min(len(err_val_sorted) - 1, int(len(err_val_sorted) * (1 - a.target_far)))
    threshold = err_val_sorted[q]

    # evaluate on ALL rows vs the real labels
    tp = fp = tn = fn = 0
    for i in range(n):
        flagged = err_all[i] > threshold
        if y[i] == 1 and flagged: tp += 1
        elif y[i] == 1 and not flagged: fn += 1
        elif y[i] == 0 and flagged: fp += 1
        else: tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    far = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    # ROC-AUC (threshold-INDEPENDENT separability) via Mann-Whitney U — the honest measure
    order = sorted(range(n), key=lambda i: err_all[i])
    ranks = [0.0] * n
    for r, i in enumerate(order, 1):
        ranks[i] = r
    npos, nneg = sum(y), n - sum(y)
    auc = ((sum(ranks[i] for i in range(n) if y[i] == 1) - npos * (npos + 1) / 2) / (npos * nneg)) if npos and nneg else 0.0
    metrics = {"roc_auc": round(auc, 4), "precision": round(prec, 4), "recall": round(rec, 4),
               "false_alarm_rate": round(far, 4), "f1": round(f1, 4),
               "threshold": round(threshold, 6), "tp": tp, "fp": fp, "tn": tn, "fn": fn}
    print(f"  threshold@far~{a.target_far}: {threshold:.5f}")
    print(f"  ROC-AUC={auc:.3f} (separability) · precision={prec:.3f} recall={rec:.3f} false_alarm={far:.3f} f1={f1:.3f}  (anomalies={sum(y)})")

    # register the model (state_dict + scaler + threshold)
    REGISTRY.mkdir(parents=True, exist_ok=True)
    vs = [int(p.name[1:]) for p in REGISTRY.glob("v*") if p.name[1:].isdigit()]
    version = (max(vs) + 1) if vs else 1
    vdir = REGISTRY / f"v{version}"; vdir.mkdir(parents=True, exist_ok=True)
    torch.save(ae.state_dict(), vdir / "autoencoder.pt")
    (vdir / "scaler.json").write_text(json.dumps({"mean": mean, "std": std, "features": feats}))
    meta = {"name": "theseus-ae", "version": version, "framework": "pytorch",
            "kind": "autoencoder-anomaly", "arch": f"{d}-{h1}-{h2}-{h1}-{d}",
            "epochs": a.epochs, "n_train_normal": len(tr_idx), **metrics, "trained_unix": time.time()}
    (vdir / "meta.json").write_text(json.dumps(meta, indent=2))
    model_sha = hashlib.sha256((vdir / "autoencoder.pt").read_bytes()).hexdigest()

    if os.environ.get("MLFLOW_TRACKING_URI"):
        try:
            import mlflow
            mlflow.set_experiment("theseus-autoencoder")
            with mlflow.start_run(run_name=f"metropt-v{version}"):
                mlflow.log_params({"framework": "pytorch", "arch": meta["arch"],
                                   "epochs": a.epochs, "target_far": a.target_far})
                mlflow.log_metrics({"precision": prec, "recall": rec, "false_alarm_rate": far, "f1": f1})
                mlflow.log_artifacts(str(vdir))
            print(f"  logged to MLflow experiment 'theseus-autoencoder' @ {os.environ['MLFLOW_TRACKING_URI']}")
        except Exception as e:
            print(f"  (MLflow log skipped: {e})")

    seal(RECORD, "model_trained", f"theseus-ae:v{version}",
         {**meta, "model_sha256": model_sha})
    print(f"  registered -> {vdir.relative_to(HERE.parent)} · sealed model_trained (autoencoder)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
