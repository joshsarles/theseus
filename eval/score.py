#!/usr/bin/env python3
"""THESEUS eval harness — anomaly-detection scorer (NV063).

Scores (track_id, is_anomaly) predictions against a labeled set (e.g. OMTAD) →
precision / recall / false-alarm rate / F1. The prediction + label contracts are defined
in eval/README.md; demo/ais_pol.py emits predictions in this shape.

  python3 eval/score.py --pred preds.csv --labels labels.csv [--out metrics.json]
  python3 eval/score.py --selftest

Label universe = the rows present in --labels. A prediction not listed (or is_anomaly=0)
counts as "not anomalous". False-alarm rate = FP / (FP + TN) — the watch-tolerance number
the NV063 strategy needs (<~1 nuisance alert per watch).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _load(path: str, idcol: str = "track_id", col: str = "is_anomaly") -> dict[str, int]:
    m: dict[str, int] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            m[str(row[idcol])] = int(float(row[col]))
    return m


def score(pred: dict[str, int], labels: dict[str, int]) -> dict:
    ids = set(labels)  # evaluate over the labeled universe
    tp = fp = fn = tn = 0
    for i in ids:
        y = labels[i]
        yh = pred.get(i, 0)  # unlisted / unflagged prediction = not-anomaly
        if y == 1 and yh == 1:
            tp += 1
        elif y == 0 and yh == 1:
            fp += 1
        elif y == 1 and yh == 0:
            fn += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    far = fp / (fp + tn) if fp + tn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    unscored = sum(1 for i in pred if i not in labels and pred[i] == 1)
    return {
        "n_labeled": len(ids), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4), "recall": round(rec, 4),
        "false_alarm_rate": round(far, 4), "f1": round(f1, 4),
        "unscored_positive_predictions": unscored,
    }


def _selftest() -> int:
    labels = {"a": 1, "b": 1, "c": 0, "d": 0, "e": 0, "f": 1}
    pred = {"a": 1, "b": 1, "c": 1, "f": 0}  # tp={a,b} fp={c} fn={f} tn={d,e}
    r = score(pred, labels)
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (2, 1, 1, 2), r
    assert r["precision"] == round(2 / 3, 4) and r["recall"] == round(2 / 3, 4), r
    assert r["false_alarm_rate"] == round(1 / 3, 4), r
    assert r["f1"] == round(2 / 3, 4), r
    print("eval selftest OK:", json.dumps(r))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS anomaly scorer (NV063).")
    ap.add_argument("--pred")
    ap.add_argument("--labels")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if not (a.pred and a.labels):
        print("need --pred and --labels (or --selftest)")
        return 2
    r = score(_load(a.pred), _load(a.labels))
    print(json.dumps(r, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
