#!/usr/bin/env python3
"""THESEUS — MetroPT-3 leave-one-failure-out CV (honest; no temporal leakage).

Replaces the temporally-leaky random-split F1 (the random split let near-identical adjacent
10-min windows of the SAME failure land in both train and test). Here: re-aggregate the raw
1 Hz stream into windows, assign each to the NEAREST of the 4 company-reported air-leak
failures (Voronoi over failure midpoints) → 4 temporal segments, each holding exactly one
failure. LOFO-CV: train on 3 segments, test on the held-out one — no window from the test
failure's time-neighborhood is ever in training. Micro-averaged window-level P/R/F1/FAR.

  python3 models/metropt_locv.py [--window 600]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "datasets" / "metropt3" / "MetroPT3(AirCompressor).csv"
SENSORS = ["TP2", "TP3", "H1", "DV_pressure", "Reservoirs", "Oil_temperature", "Motor_current",
           "COMP", "DV_eletric", "Towers", "MPG", "LPS", "Pressure_switch", "Oil_level", "Caudal_impulses"]
FAILURES = [("2020-04-18 00:00:00", "2020-04-18 23:59:00"),
            ("2020-05-29 23:30:00", "2020-05-30 06:00:00"),
            ("2020-06-05 10:00:00", "2020-06-07 14:30:00"),
            ("2020-07-15 14:30:00", "2020-07-15 19:00:00")]


def _ts(s):
    return datetime.fromisoformat(s).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=600)
    a = ap.parse_args()
    if not SRC.exists():
        print(f"missing {SRC}")
        return 1
    fails = [(_ts(s), _ts(e)) for s, e in FAILURES]
    mids = [(s + e) / 2 for s, e in fails]

    sums = defaultdict(lambda: [0.0] * len(SENSORS))
    counts = defaultdict(int)
    with SRC.open() as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.fromisoformat(row["timestamp"]).timestamp()
            except (ValueError, KeyError):
                continue
            b = int(t // a.window)
            acc = sums[b]
            ok = True
            for i, s in enumerate(SENSORS):
                try:
                    acc[i] += float(row[s])
                except (ValueError, KeyError):
                    ok = False
                    break
            if ok:
                counts[b] += 1

    W = []  # (features, is_anomaly, nearest-failure-segment)
    for b in sorted(counts):
        n = counts[b]
        center = b * a.window + a.window / 2
        feats = [sums[b][i] / n for i in range(len(SENSORS))]
        is_anom = 1 if any(s <= center <= e for s, e in fails) else 0
        seg = min(range(len(mids)), key=lambda k: abs(center - mids[k]))
        W.append((feats, is_anom, seg))

    from sklearn.ensemble import GradientBoostingClassifier
    agg = dict(tp=0, fp=0, fn=0, tn=0)
    per_fold = []
    for k in range(4):
        tr = [(f, y) for f, y, s in W if s != k]
        te = [(f, y) for f, y, s in W if s == k]
        ytr = [y for _, y in tr]
        yte = [y for _, y in te]
        if not te or sum(ytr) == 0 or sum(yte) == 0:
            per_fold.append({"fold": k + 1, "skip": "degenerate", "n_test": len(te), "pos_test": sum(yte)})
            continue
        m = GradientBoostingClassifier(random_state=k).fit([f for f, _ in tr], ytr)
        pred = list(m.predict([f for f, _ in te]))
        tp = sum(1 for p, t in zip(pred, yte) if p == 1 and t == 1)
        fp = sum(1 for p, t in zip(pred, yte) if p == 1 and t == 0)
        fn = sum(1 for p, t in zip(pred, yte) if p == 0 and t == 1)
        tn = sum(1 for p, t in zip(pred, yte) if p == 0 and t == 0)
        for kk, v in dict(tp=tp, fp=fp, fn=fn, tn=tn).items():
            agg[kk] += v
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        per_fold.append({"fold": k + 1, "n_test": len(te), "pos_test": sum(yte),
                         "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                         "precision": round(pr, 3), "recall": round(rc, 3)})

    tp, fp, fn, tn = agg["tp"], agg["fp"], agg["fn"], agg["tn"]
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F1 = 2 * P * R / (P + R) if P + R else 0.0
    FAR = fp / (fp + tn) if fp + tn else 0.0
    out = {"protocol": "leave-one-failure-out CV (4 folds; nearest-failure temporal segments)",
           "n_windows": len(W), "window_s": a.window,
           "micro": {"precision": round(P, 3), "recall": round(R, 3), "f1": round(F1, 3),
                     "false_alarm_rate": round(FAR, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn},
           "per_fold": per_fold}
    print(json.dumps(out, indent=2))
    (Path(__file__).resolve().parent / "metropt_locv_results.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
