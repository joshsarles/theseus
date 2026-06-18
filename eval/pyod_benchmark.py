#!/usr/bin/env python3
"""THESEUS — PyOD benchmark wrap (INTEGRATION_SPEC §7 adopt #2).

Runs the THESEUS detector signals INSIDE PyOD's orchestration so the NV063 / PdM numbers are
benchmarked against a field of standard detectors, not a bespoke score in isolation. PyOD
(yzhao062, BSD-2, 60+ detectors) is the recognized anomaly-detection benchmark harness; this
script makes the THESEUS autoencoder a row in that field on the SAME real data.

Two REAL datasets, two honest comparisons:

  PdM (machinery — the "ship's doctor" autoencoder):
    data  : ingest/out/metropt.csv  (MetroPT-3 real compressor failures; 15 feats, ~498 labeled
            anomalies / ~25.5k rows)
    field : PyOD AutoEncoder (the orchestrated twin of demo/autoencoder.py) vs IForest, ECOD,
            COPOD, KNN, LOF, OCSVM, PCA. Unsupervised: fit on the feature matrix, score all rows,
            evaluate against the REAL labels. ROC-AUC (threshold-free) is the headline; PR-AUC +
            precision@k + precision/recall/FAR at a contamination-set threshold reported too.

  NV063 (AIS Pattern-of-Life):
    data  : eval/out/curate_candidates.csv joined to eval/curated_labels.csv  (the n=50
            analyst-curated set — the HONEST NV063 ground truth, 9 pos / 41 neg)
    field : the SAME PyOD detectors on the per-track features (n_fixes, dur_h, sog stats,
            still_frac, max_gap_min, max_jump_kn) vs the n=50 labels — PLUS the bespoke
            rule-based demo/ais_pol.py detector's own number (from the `aispol_flag` column)
            in the same table, for a true apples-to-apples comparison.

ALL REAL — no fabricated metrics. Small-n caveats stated loudly. Read-only on all inputs;
writes only under eval/out/. Reuses eval/score.py's definitions (precision / recall /
false_alarm_rate = FP/(FP+TN) / F1) so the numbers are consistent with the existing harness.

  python3 eval/pyod_benchmark.py                       # both datasets, write eval/out/pyod_benchmark.json
  python3 eval/pyod_benchmark.py --dataset pdm         # machinery only
  python3 eval/pyod_benchmark.py --dataset nv063       # AIS PoL only
  python3 eval/pyod_benchmark.py --epochs 30 --seed 316

Requires: pyod, scikit-learn, numpy, torch (AutoEncoder). A clean venv is fine; if PyOD is
absent the script says so honestly and exits non-zero (never fabricates a number).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
METROPT = ROOT / "ingest" / "out" / "metropt.csv"
AIS_CANDIDATES = HERE / "out" / "curate_candidates.csv"
AIS_LABELS = HERE / "curated_labels.csv"
AIS_CURATED_METRICS = HERE / "out" / "curated_metrics.json"   # canonical post-fix ais_pol number
OUT = HERE / "out" / "pyod_benchmark.json"

LABEL = "is_anomaly"


def _need(msg: str) -> "tuple":
    print(f"  [PyOD benchmark] MISSING DEPENDENCY: {msg}", file=sys.stderr)
    print("  install into a venv:  pip install pyod scikit-learn numpy torch tqdm", file=sys.stderr)
    raise SystemExit(3)


def _detectors(contamination: float, seed: int, epochs: int, n_features: int,
               n_samples: int) -> dict:
    """The PyOD field. AutoEncoder is the orchestrated twin of demo/autoencoder.py.

    All share the PyOD base API: .fit(X) -> .decision_scores_ (train) / .decision_function(X).
    Higher score = more anomalous (PyOD convention).
    """
    try:
        from pyod.models.iforest import IForest
        from pyod.models.ecod import ECOD
        from pyod.models.copod import COPOD
        from pyod.models.knn import KNN
        from pyod.models.lof import LOF
        from pyod.models.ocsvm import OCSVM
        from pyod.models.pca import PCA
    except ImportError as e:  # pragma: no cover
        _need(f"pyod core ({e})")
    det = {
        "IForest": IForest(contamination=contamination, random_state=seed),
        "ECOD": ECOD(contamination=contamination),
        "COPOD": COPOD(contamination=contamination),
        "KNN": KNN(contamination=contamination),
        "LOF": LOF(contamination=contamination),
        "OCSVM": OCSVM(contamination=contamination),
        "PCA": PCA(contamination=contamination, random_state=seed),
    }
    # AutoEncoder needs torch; include it as the THESEUS detector-of-record. Hidden layers mirror
    # demo/autoencoder.py's funnel (d -> d/2 -> d/4) so the comparison is faithful to our model.
    try:
        from pyod.models.auto_encoder import AutoEncoder
        h1, h2 = max(2, n_features // 2), max(2, n_features // 4)
        # batch_size must not exceed the sample count, or PyOD's DataLoader yields zero batches
        # (UnboundLocalError 'loss') on small sets like the n=50 NV063 curated set.
        batch = max(1, min(64, n_samples))
        det["AutoEncoder(THESEUS)"] = AutoEncoder(
            contamination=contamination, epoch_num=epochs, batch_size=batch,
            hidden_neuron_list=[h1, h2], lr=1e-3, preprocessing=True,
        )
    except ImportError as e:  # torch missing -> run the rest honestly, note the gap
        print(f"  [PyOD benchmark] note: AutoEncoder skipped (torch unavailable: {e})", file=sys.stderr)
    return det


def _metrics_from_labels(y: list[int], yhat: list[int]) -> dict:
    """precision / recall / false_alarm_rate / f1 — SAME definitions as eval/score.py."""
    tp = fp = fn = tn = 0
    for yi, yh in zip(y, yhat):
        if yi == 1 and yh == 1: tp += 1
        elif yi == 0 and yh == 1: fp += 1
        elif yi == 1 and yh == 0: fn += 1
        else: tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    far = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "false_alarm_rate": round(far, 4), "f1": round(f1, 4)}


def _rank_metrics(y, scores) -> dict:
    """Threshold-FREE separability: ROC-AUC + PR-AUC (average precision) + precision@k (k=#pos)."""
    import numpy as np
    from sklearn.metrics import roc_auc_score, average_precision_score
    from pyod.utils.utility import precision_n_scores
    y = np.asarray(y); s = np.asarray(scores, dtype=float)
    out = {}
    if y.sum() and (len(y) - y.sum()):
        out["roc_auc"] = round(float(roc_auc_score(y, s)), 4)
        out["pr_auc"] = round(float(average_precision_score(y, s)), 4)
        out["precision_at_k"] = round(float(precision_n_scores(y, s)), 4)  # k = #positives
    else:
        out["roc_auc"] = out["pr_auc"] = out["precision_at_k"] = None
    return out


def _run_field(X, y, contamination, seed, epochs) -> dict:
    """Fit every PyOD detector on X (unsupervised), score all rows, evaluate vs y."""
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    Xs = StandardScaler().fit_transform(np.asarray(X, dtype=float))
    rows = {}
    for name, clf in _detectors(contamination, seed, epochs, Xs.shape[1], Xs.shape[0]).items():
        clf.fit(Xs)
        scores = clf.decision_scores_           # train-set scores (unsupervised: train == eval set)
        yhat = clf.labels_.tolist()             # PyOD's contamination-thresholded labels
        rows[name] = {**_rank_metrics(y, scores), **_metrics_from_labels(y, yhat),
                      "threshold": "contamination=%.4f" % contamination}
    return rows


# ---------------------------------------------------------------------------
# PdM (machinery) — MetroPT
# ---------------------------------------------------------------------------
def _load_metropt(path: Path):
    rows = list(csv.DictReader(path.open()))
    feats = []
    for c in rows[0]:
        if c == LABEL:
            continue
        try:
            vals = [float(r[c]) for r in rows]
        except ValueError:
            continue
        if len(set(vals)) > 1:               # numeric, non-constant (same filter as demo/autoencoder.py)
            feats.append(c)
    X = [[float(r[c]) for c in feats] for r in rows]
    y = [int(float(r.get(LABEL, 0))) for r in rows]
    return X, y, feats


def bench_pdm(seed: int, epochs: int) -> dict:
    if not METROPT.exists():
        print(f"  [PyOD benchmark] PdM data not found: {METROPT} (run ingest first)", file=sys.stderr)
        return {"error": f"missing {METROPT}"}
    X, y, feats = _load_metropt(METROPT)
    contamination = max(1e-4, min(0.49, sum(y) / len(y)))   # real base rate
    print(f"PdM (machinery) · MetroPT-3 · {len(X):,} rows × {len(feats)} feats · "
          f"{sum(y)} real anomalies ({100*sum(y)/len(y):.2f}%)")
    field = _run_field(X, y, contamination, seed, epochs)
    return {
        "dataset": "MetroPT-3 machinery (real labeled compressor failures)",
        "source": str(METROPT.relative_to(ROOT)),
        "n_rows": len(X), "n_features": len(feats), "n_anomalies": sum(y),
        "base_rate": round(sum(y) / len(y), 4), "contamination_used": round(contamination, 4),
        "features": feats, "detectors": field,
        "headline_metric": "roc_auc",
        "note": "Unsupervised: every detector fit on the feature matrix, scored, evaluated vs REAL "
                "labels. AutoEncoder(THESEUS) is the PyOD-orchestrated twin of demo/autoencoder.py. "
                "ROC-AUC is threshold-free; precision/recall/FAR are at the contamination threshold.",
    }


# ---------------------------------------------------------------------------
# NV063 (AIS PoL) — curated n=50
# ---------------------------------------------------------------------------
AIS_FEATURES = ["n_fixes", "dur_h", "sog_min", "sog_mean", "sog_max",
                "still_frac", "max_gap_min", "max_jump_kn", "vessel_type"]


def _load_ais():
    labs = {str(r["track_id"]): int(float(r[LABEL]))
            for r in csv.DictReader(AIS_LABELS.open())}
    cands = {str(r["track_id"]): r for r in csv.DictReader(AIS_CANDIDATES.open())}
    ids = [i for i in cands if i in labs]            # joinable, label universe = curated set
    X, y, aispol = [], [], []
    for i in ids:
        r = cands[i]
        row = []
        for c in AIS_FEATURES:
            try:
                row.append(float(r[c]))
            except (ValueError, KeyError):
                row.append(0.0)
        X.append(row)
        y.append(labs[i])
        aispol.append(int(float(r.get("aispol_flag", 0) or 0)))   # bespoke detector's own call
    return X, y, aispol, ids


def bench_nv063(seed: int, epochs: int) -> dict:
    if not (AIS_CANDIDATES.exists() and AIS_LABELS.exists()):
        print(f"  [PyOD benchmark] NV063 data not found ({AIS_CANDIDATES} / {AIS_LABELS})",
              file=sys.stderr)
        return {"error": "missing AIS candidate/label files"}
    X, y, aispol, ids = _load_ais()
    npos = sum(y)
    contamination = max(1e-4, min(0.49, npos / len(y)))
    print(f"NV063 (AIS PoL) · curated n={len(y)} · {npos} pos / {len(y)-npos} neg · "
          f"{len(AIS_FEATURES)} per-track feats")
    field = _run_field(X, y, contamination, seed, epochs)

    # The bespoke rule-based detector (demo/ais_pol.py) as a row in the SAME table.
    # The `aispol_flag` column in curate_candidates.csv is the PRE-fix detector (P=0.36/R=1.0);
    # the canonical, current number is the POST-fix run in eval/out/curated_metrics.json
    # (P=0.57/R=0.89, the eval/RESULTS.md + ROADMAP headline). Prefer the canonical file; fall
    # back to the stale column only if it is absent, and label which one we used honestly.
    stale = {**_metrics_from_labels(y, aispol)}
    bespoke_post = None
    if AIS_CURATED_METRICS.exists():
        try:
            cm = json.loads(AIS_CURATED_METRICS.read_text())
            bespoke_post = {
                "tp": cm.get("tp"), "fp": cm.get("fp"), "fn": cm.get("fn"), "tn": cm.get("tn"),
                "precision": cm.get("precision"), "recall": cm.get("recall"),
                "false_alarm_rate": cm.get("false_alarm_rate"), "f1": cm.get("f1"),
                "roc_auc": None, "pr_auc": None, "precision_at_k": None,
                "threshold": "rule-based (demo/ais_pol.py, POST-fix) — canonical curated_metrics.json",
            }
        except Exception:
            bespoke_post = None
    if bespoke_post:
        field["ais_pol(THESEUS rules)"] = bespoke_post
        field["ais_pol(THESEUS rules, PRE-fix)"] = {
            **stale, "roc_auc": None, "pr_auc": None, "precision_at_k": None,
            "threshold": "rule-based (PRE-fix aispol_flag column, kept for the bug-fix baseline)",
        }
    else:
        field["ais_pol(THESEUS rules)"] = {
            **stale, "roc_auc": None, "pr_auc": None, "precision_at_k": None,
            "threshold": "rule-based (demo/ais_pol.py aispol_flag column)",
        }
    return {
        "dataset": "AIS Pattern-of-Life — analyst-curated n=50 (NV063 honest ground truth)",
        "source": f"{AIS_CANDIDATES.relative_to(ROOT)} ⨝ {AIS_LABELS.relative_to(ROOT)}",
        "n_rows": len(y), "n_features": len(AIS_FEATURES), "n_anomalies": npos,
        "base_rate": round(npos / len(y), 4), "contamination_used": round(contamination, 4),
        "features": AIS_FEATURES, "detectors": field,
        "headline_metric": "roc_auc",
        "note": "SMALL-N (n=50, 9 pos): treat as a pilot signal, not a production metric — wide CIs, "
                "results sensitive to single tracks; matches eval/RESULTS.md §2 caveats. "
                "ais_pol(THESEUS rules) is the bespoke rule detector's OWN canonical POST-fix n=50 "
                "number (P=0.57/R=0.89/FAR=0.15, eval/out/curated_metrics.json); the PRE-fix row "
                "(P=0.36/R=1.0) is the stale aispol_flag column kept to show the SOG+cadence bug fix. "
                "The PyOD rows are GENERIC unsupervised detectors on the same per-track features "
                "(no AIS domain rules) — they set the 'what does an off-the-shelf detector get' bar; "
                "the bespoke rules trade precision for recall (R=0.89), the watch-officer-relevant axis.",
    }


def _print_table(title: str, block: dict) -> None:
    if "error" in block:
        print(f"\n{title}: {block['error']}")
        return
    print(f"\n{title}  ({block['dataset']})")
    hdr = f"  {'detector':<22} {'ROC-AUC':>8} {'PR-AUC':>7} {'P@k':>6} {'prec':>6} {'rec':>6} {'FAR':>6} {'F1':>6}"
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    det = block["detectors"]
    # sort by ROC-AUC desc (None last)
    def _key(kv):
        v = kv[1].get("roc_auc")
        return (-(v if v is not None else -1),)
    for name, m in sorted(det.items(), key=_key):
        def f(x): return f"{x:>.3f}" if isinstance(x, (int, float)) else f"{'—':>5}"
        print(f"  {name:<22} {f(m.get('roc_auc')):>8} {f(m.get('pr_auc')):>7} {f(m.get('precision_at_k')):>6} "
              f"{m['precision']:>6.3f} {m['recall']:>6.3f} {m['false_alarm_rate']:>6.3f} {m['f1']:>6.3f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS PyOD benchmark (NV063 + PdM).")
    ap.add_argument("--dataset", choices=["pdm", "nv063", "both"], default="both")
    ap.add_argument("--epochs", type=int, default=30, help="AutoEncoder epochs (default 30)")
    ap.add_argument("--seed", type=int, default=316)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    try:
        import pyod  # noqa: F401
    except ImportError:
        _need("pyod (the whole point of this benchmark)")

    import numpy as np
    np.random.seed(a.seed)
    try:
        import torch
        torch.manual_seed(a.seed)
    except ImportError:
        pass

    print("THESEUS · PyOD benchmark wrap — real data, real comparative numbers (no fabrication)\n")
    result = {"seed": a.seed, "epochs": a.epochs}
    import pyod as _p
    result["pyod_version"] = getattr(_p, "__version__", "unknown")

    if a.dataset in ("pdm", "both"):
        result["pdm"] = bench_pdm(a.seed, a.epochs)
        _print_table("PdM machinery benchmark", result["pdm"])
    if a.dataset in ("nv063", "both"):
        result["nv063"] = bench_nv063(a.seed, a.epochs)
        _print_table("NV063 AIS PoL benchmark", result["nv063"])

    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nwrote {outp.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
