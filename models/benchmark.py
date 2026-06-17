#!/usr/bin/env python3
"""THESEUS — machinery model benchmarks (real, reproducible, sklearn-only).

REPRODUCTION benchmarks from the local data (`ingest/out/*.csv` + raw C-MAPSS). These are
independent of Tommy's MLflow/loop runs (his server isn't reachable from this shell); CBM
cross-checks the loop registry (`demo/registry/theseus-cbm` RMSE 0.003823). Honest baselines
included so the numbers mean something.

  python3 models/benchmark.py   # prints + writes models/benchmark_results.json
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ING = ROOT / "ingest" / "out"


def _rmse(p, y):
    return (sum((a - b) ** 2 for a, b in zip(p, y)) / len(y)) ** 0.5


def _load(name):
    rows = list(csv.DictReader((ING / name).open()))
    return rows, list(rows[0].keys())


def bench_cbm():
    rows, h = _load("cbm.csv")
    random.Random(316).shuffle(rows)
    non = {"gt_compressor_decay", "gt_turbine_decay"}
    feats = [c for c in h if c not in non]
    feats = [c for c in feats if len({r[c] for r in rows}) > 1]
    X = [[float(r[c]) for c in feats] for r in rows]
    y = [float(r["gt_compressor_decay"]) for r in rows]
    cut = int(0.8 * len(X))
    from sklearn.ensemble import GradientBoostingRegressor
    m = GradientBoostingRegressor(random_state=316).fit(X[:cut], y[:cut])
    rmse = _rmse(list(m.predict(X[cut:])), y[cut:])
    base = _rmse([sum(y[:cut]) / cut] * len(y[cut:]), y[cut:])
    return {"dataset": "UCI #316 CBM (naval gas turbine)", "task": "regression: gt_compressor_decay",
            "n": len(rows), "features": len(feats), "metric": "RMSE", "value": round(rmse, 5),
            "mean_baseline_RMSE": round(base, 5), "split": "random 80/20",
            "note": "cross-checks loop registry RMSE 0.003823"}


def bench_cmapss():
    src = ROOT / "data" / "datasets" / "cmapss" / "train_FD001.txt"
    raw = []
    maxc = defaultdict(int)
    for line in src.read_text().splitlines():
        p = line.split()
        if len(p) < 26:
            continue
        u, c = int(float(p[0])), int(float(p[1]))
        raw.append((u, c, [float(x) for x in p[2:26]]))
        maxc[u] = max(maxc[u], c)
    tr = [(v, maxc[u] - c) for u, c, v in raw if u <= 80]
    te = [(v, maxc[u] - c) for u, c, v in raw if u > 80]
    from sklearn.ensemble import GradientBoostingRegressor
    m = GradientBoostingRegressor(random_state=1).fit([v for v, _ in tr], [r for _, r in tr])
    yte = [r for _, r in te]
    rmse = _rmse(list(m.predict([v for v, _ in te])), yte)
    base = _rmse([sum(r for _, r in tr) / len(tr)] * len(yte), yte)
    return {"dataset": "NASA C-MAPSS FD001", "task": "regression: RUL (cycles)", "n": len(raw),
            "metric": "RMSE(cycles)", "value": round(rmse, 2), "mean_baseline_RMSE": round(base, 2),
            "split": "unit-split (train units 1-80 / test 81-100)",
            "note": "internal split on train file; not the official test-set/RUL leaderboard protocol"}


def bench_metropt():
    rows, h = _load("metropt.csv")
    feats = [c for c in h if c != "is_anomaly"]
    feats = [c for c in feats if len({r[c] for r in rows}) > 1]
    X = [[float(r[c]) for c in feats] for r in rows]
    y = [int(float(r["is_anomaly"])) for r in rows]
    cut = int(0.8 * len(X))
    Xtr, ytr, Xte, yte = X[:cut], y[:cut], X[cut:], y[cut:]
    split = "time-ordered 80/20"
    if sum(ytr) == 0 or sum(yte) == 0:
        idx = list(range(len(X)))
        random.Random(7).shuffle(idx)
        Xtr = [X[i] for i in idx[:cut]]; ytr = [y[i] for i in idx[:cut]]
        Xte = [X[i] for i in idx[cut:]]; yte = [y[i] for i in idx[cut:]]
        split = "random 80/20 (time-split left a class empty)"
    from sklearn.ensemble import GradientBoostingClassifier
    m = GradientBoostingClassifier(random_state=7).fit(Xtr, ytr)
    pred = list(m.predict(Xte))
    tp = sum(1 for p, t in zip(pred, yte) if p == 1 and t == 1)
    fp = sum(1 for p, t in zip(pred, yte) if p == 1 and t == 0)
    fn = sum(1 for p, t in zip(pred, yte) if p == 0 and t == 1)
    tn = sum(1 for p, t in zip(pred, yte) if p == 0 and t == 0)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    far = fp / (fp + tn) if fp + tn else 0.0
    return {"dataset": "MetroPT-3 (air compressor)", "task": "classification: is_anomaly (real air-leak windows)",
            "n": len(rows), "base_rate": round(sum(y) / len(y), 4), "features": len(feats),
            "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
            "false_alarm_rate": round(far, 4), "split": split,
            "note": "supervised baseline; unsupervised autoencoder (Tommy's direction) is the deeper anomaly model"}


def main() -> int:
    out = [bench_cbm(), bench_cmapss(), bench_metropt()]
    print(json.dumps(out, indent=2))
    (Path(__file__).resolve().parent / "benchmark_results.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
