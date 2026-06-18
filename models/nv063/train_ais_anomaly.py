#!/usr/bin/env python3
"""THESEUS NV063 — train a deployable AIS Pattern-of-Life anomaly model (Pi 5 / 4GB).

The headline mission today rests on the rule-based demo/ais_pol.py. This trains a compact,
explainable, UNSUPERVISED ML detector (IsolationForest) on the FULL MarineCadastre track
population, then evaluates it HONESTLY against the analyst-curated n=50 set with ais_pol as
the baseline — and exports it to ONNX (+int8) with a Pi-5-4GB resource benchmark.

Discipline:
  * Features are re-extracted from raw AIS with the EXACT definitions used by
    eval/curate_oparea.py, so the curated 50 are a labeled subset of the training pool with
    identical features (no schema drift, no leakage).
  * The 50 curated track_ids are EXCLUDED from the fit (no train-on-test).
  * Unsupervised: labels are used ONLY for eval. Metric definitions match eval/score.py.
  * Honest small-n caveats: n=50 (9 pos), pilot signal, SME-pending — same as eval/RESULTS.md.

  python3 models/nv063/train_ais_anomaly.py [--rows N] [--contamination 0.06] [--n-estimators 200]

Writes:
  models/nv063/model.pkl            sklearn Pipeline(StandardScaler, IsolationForest)
  models/nv063/meta.json            features, params, sha256, curated metrics, pool alert rate
  models/nv063/results.json         full eval + Pi resource benchmark
  models/onnx/ais_anomaly_iforest.onnx (+ _int8.onnx)   edge artifacts
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pickle
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RAW = ROOT / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
LABELS = ROOT / "eval" / "curated_labels.csv"
CURATED_METRICS = ROOT / "eval" / "out" / "curated_metrics.json"
ONNX_DIR = ROOT / "models" / "onnx"

FEATURES = ["n_fixes", "dur_h", "sog_min", "sog_mean", "sog_max",
            "still_frac", "max_gap_min", "max_jump_kn", "vessel_type"]
MIN_FIXES = 6  # same eligibility as eval/curate_oparea.py


def _hav_nm(la0, lo0, la1, lo1):
    R = 3440.065
    a, b, c, d = map(math.radians, (la0, lo0, la1, lo1))
    h = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def extract_tracks(rows_cap: int) -> dict[str, dict]:
    """Per-track features from raw AIS — EXACT defs from eval/curate_oparea.py."""
    tracks: dict[str, list] = defaultdict(list)
    n = 0
    with RAW.open() as f:
        for row in csv.DictReader(f):
            n += 1
            if n > rows_cap:
                break
            try:
                lat, lon, sog = float(row["LAT"]), float(row["LON"]), float(row["SOG"])
                t = datetime.fromisoformat(row["BaseDateTime"]).timestamp()
            except (ValueError, KeyError):
                continue
            try:
                vt = int(float(row.get("VesselType") or -1))
            except ValueError:
                vt = -1
            tracks[row["MMSI"]].append((t, lat, lon, sog, vt))

    feats: dict[str, dict] = {}
    for mmsi, fx in tracks.items():
        if len(fx) < MIN_FIXES:
            continue
        fx.sort()
        sogs = [x[3] for x in fx]
        span_h = (fx[-1][0] - fx[0][0]) / 3600
        still = sum(1 for x in fx if x[3] < 0.5)
        mg = mj = 0.0
        for (t0, la0, lo0, s0, _), (t1, la1, lo1, s1, _) in zip(fx, fx[1:]):
            dt = t1 - t0
            if dt <= 0:
                continue
            mg = max(mg, dt / 60)
            mj = max(mj, _hav_nm(la0, lo0, la1, lo1) / (dt / 3600))
        feats[mmsi] = {
            "n_fixes": len(fx), "dur_h": span_h,
            "sog_min": min(sogs), "sog_mean": statistics.fmean(sogs), "sog_max": max(sogs),
            "still_frac": still / len(fx), "max_gap_min": mg, "max_jump_kn": mj,
            "vessel_type": fx[0][4],
        }
    return feats, n


def _metrics(y: list[int], yhat: list[int]) -> dict:
    """precision / recall / false_alarm_rate / f1 — eval/score.py definitions."""
    tp = sum(1 for a, b in zip(y, yhat) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y, yhat) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y, yhat) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(y, yhat) if a == 0 and b == 0)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    far = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 4),
            "recall": round(rec, 4), "false_alarm_rate": round(far, 4), "f1": round(f1, 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Train deployable NV063 AIS anomaly model.")
    ap.add_argument("--rows", type=int, default=1_500_000)
    ap.add_argument("--contamination", type=float, default=0.06)  # honest population estimate (RESULTS.md)
    ap.add_argument("--n-estimators", type=int, default=200)
    ap.add_argument("--seed", type=int, default=316)
    a = ap.parse_args()
    if not RAW.exists():
        print(f"  raw AIS missing: {RAW}"); return 1

    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score, average_precision_score

    print("THESEUS NV063 · deployable AIS Pattern-of-Life anomaly model")
    t0 = time.time()
    feats, scanned = extract_tracks(a.rows)
    print(f"  extracted {len(feats):,} eligible tracks (≥{MIN_FIXES} fixes) from {scanned:,} raw rows "
          f"in {time.time()-t0:.1f}s")

    labels = {str(r["track_id"]): int(float(r["is_anomaly"]))
              for r in csv.DictReader(LABELS.open())}
    eval_ids = [i for i in labels if i in feats]
    missing = [i for i in labels if i not in feats]
    if missing:
        print(f"  note: {len(missing)} curated ids not in pool (cap/eligibility) — scored on {len(eval_ids)}")

    def vec(d: dict) -> list[float]:
        return [float(d[k]) for k in FEATURES]

    train_ids = [m for m in feats if m not in labels]      # exclude curated 50 (no train-on-test)
    X_train = np.array([vec(feats[m]) for m in train_ids], dtype=float)
    X_eval = np.array([vec(feats[m]) for m in eval_ids], dtype=float)
    y_eval = [labels[m] for m in eval_ids]

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("iforest", IsolationForest(n_estimators=a.n_estimators, contamination=a.contamination,
                                    random_state=a.seed, n_jobs=-1)),
    ])
    t1 = time.time()
    pipe.fit(X_train)
    fit_s = time.time() - t1
    print(f"  fit IsolationForest(n={a.n_estimators}, contamination={a.contamination}) on "
          f"{len(train_ids):,} tracks in {fit_s:.2f}s")

    # sklearn predictions on the curated set: predict() = 1 inlier / -1 outlier; score_samples lower = more anomalous
    skl_lab = pipe.predict(X_eval)
    yhat = [1 if v == -1 else 0 for v in skl_lab]
    anom_score = [-float(s) for s in pipe.score_samples(X_eval)]  # higher = more anomalous
    m = _metrics(y_eval, yhat)
    roc = round(float(roc_auc_score(y_eval, anom_score)), 4) if 0 < sum(y_eval) < len(y_eval) else None
    pr = round(float(average_precision_score(y_eval, anom_score)), 4) if 0 < sum(y_eval) < len(y_eval) else None

    # pool-wide alert rate (vs ais_pol's 1,029/11,898 = 8.6%)
    pool_lab = pipe.predict(np.array([vec(feats[m_]) for m_ in feats], dtype=float))
    pool_flagged = int((pool_lab == -1).sum())

    baseline = {}
    if CURATED_METRICS.exists():
        cm = json.loads(CURATED_METRICS.read_text())
        baseline = {k: cm.get(k) for k in ("precision", "recall", "f1", "false_alarm_rate")}

    print(f"  curated n={len(y_eval)} ({sum(y_eval)} pos): "
          f"P={m['precision']} R={m['recall']} F1={m['f1']} FAR={m['false_alarm_rate']} | "
          f"ROC-AUC={roc} PR-AUC={pr}")
    print(f"  baseline ais_pol (rules): {baseline}")
    print(f"  pool alerts: {pool_flagged}/{len(feats)} ({100*pool_flagged/len(feats):.1f}%) "
          f"vs ais_pol 8.6%")

    # ---- persist sklearn model + meta ----
    HERE.mkdir(parents=True, exist_ok=True)
    blob = pickle.dumps(pipe)
    (HERE / "model.pkl").write_bytes(blob)
    model_sha = hashlib.sha256(blob).hexdigest()

    # ---- ONNX export (+ int8) + Pi resource benchmark ----
    onnx_report = export_and_bench(pipe, X_eval, yhat, anom_score)

    meta = {
        "name": "theseus-nv063-ais-anomaly", "model": "IsolationForest+StandardScaler",
        "framework": "sklearn", "features": FEATURES, "n_estimators": a.n_estimators,
        "contamination": a.contamination, "seed": a.seed,
        "n_train": len(train_ids), "n_eval": len(y_eval),
        "model_sha256": model_sha, "trained_unix": time.time(),
    }
    (HERE / "meta.json").write_text(json.dumps(meta, indent=2))

    results = {
        "dataset": "MarineCadastre US AIS 2024-01-01 (public domain) — per-track Pattern-of-Life",
        "n_pool": len(feats), "n_train": len(train_ids), "scanned_rows": scanned,
        "curated_eval": {"n": len(y_eval), "n_pos": sum(y_eval), **m,
                         "roc_auc": roc, "pr_auc": pr},
        "baseline_ais_pol_rules": baseline,
        "pool_alert_rate": {"flagged": pool_flagged, "total": len(feats),
                            "pct": round(100 * pool_flagged / len(feats), 2), "ais_pol_pct": 8.6},
        "fit_seconds": round(fit_s, 3),
        "edge": onnx_report,
        "caveats": "n=50 (9 pos) analyst-curated, pilot signal, SME-pending (matches eval/RESULTS.md). "
                   "Unsupervised IForest fit on the pool EXCLUDING the 50; labels used only for eval. "
                   "ROC-AUC/PR-AUC are threshold-free; P/R/FAR at contamination threshold.",
    }
    (HERE / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  wrote models/nv063/{{model.pkl, meta.json, results.json}} (sha256={model_sha[:12]}…)")
    return 0


def export_and_bench(pipe, X_eval, skl_yhat, skl_score) -> dict:
    """skl2onnx export (+ int8 dynamic quant) + Pi-5-4GB resource benchmark (1-thread CPU)."""
    rep: dict = {"onnx": None}
    try:
        from skl2onnx import to_onnx
        import onnxruntime as ort
        import resource
    except ImportError as e:
        rep["error"] = f"onnx export skipped (missing dep): {e}"
        print(f"  [onnx] skipped: {e}")
        return rep

    ONNX_DIR.mkdir(parents=True, exist_ok=True)
    fp32 = ONNX_DIR / "ais_anomaly_iforest.onnx"
    int8 = ONNX_DIR / "ais_anomaly_iforest_int8.onnx"
    Xf = X_eval.astype(np.float32)
    try:
        # IsolationForest emits ai.onnx.ml ops; onnxruntime supports that domain at opset 3.
        onx = to_onnx(pipe, Xf[:1], target_opset={"": 17, "ai.onnx.ml": 3})
        fp32.write_bytes(onx.SerializeToString())
    except Exception as e:
        rep["error"] = f"skl2onnx conversion failed: {e}"
        print(f"  [onnx] conversion failed: {e}")
        return rep

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1          # mimic a single Pi core
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(fp32.as_posix(), so, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    out_names = [o.name for o in sess.get_outputs()]

    # parity (ONNX label vs sklearn label) + per-track latency
    res = sess.run(None, {in_name: Xf})
    onnx_label = np.asarray(res[0]).reshape(-1)
    onnx_yhat = [1 if int(v) == -1 else 0 for v in onnx_label]
    parity = float(np.mean([a == b for a, b in zip(onnx_yhat, skl_yhat)]))

    # single-row latency (worst case for an onboard per-track call)
    one = Xf[:1]
    for _ in range(20):
        sess.run(None, {in_name: one})
    t = time.time()
    N = 500
    for _ in range(N):
        sess.run(None, {in_name: one})
    lat_ms = (time.time() - t) / N * 1000
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)  # macOS: bytes

    rep["onnx"] = {
        "fp32_path": str(fp32.relative_to(ROOT)), "fp32_bytes": fp32.stat().st_size,
        "onnx_vs_sklearn_label_parity": round(parity, 4),
        "single_row_latency_ms_1thread": round(lat_ms, 4),
        "training_process_peak_rss_mb": round(peak_rss_mb, 1),
        "rss_note": "this RSS is the full TRAINING process (sklearn+numpy+onnxruntime); the honest "
                    "Pi inference-only footprint is in models/nv063/pi_bench.json (~74 MB).",
        "out_names": out_names,
    }
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
        quantize_dynamic(fp32.as_posix(), int8.as_posix(), weight_type=QuantType.QInt8)
        rep["onnx"]["int8_path"] = str(int8.relative_to(ROOT))
        rep["onnx"]["int8_bytes"] = int8.stat().st_size
        rep["onnx"]["int8_note"] = ("dynamic quant targets MatMul/Gemm; a TreeEnsemble stores float "
                                    "thresholds, so size change is expected to be small — fp32 is "
                                    "already tiny for the Pi.")
    except Exception as e:
        rep["onnx"]["int8_note"] = f"int8 quant skipped/limited: {e}"

    o = rep["onnx"]
    print(f"  [onnx] fp32={o['fp32_bytes']/1024:.1f} KB · parity={o['onnx_vs_sklearn_label_parity']} · "
          f"latency={o['single_row_latency_ms_1thread']:.3f} ms/track (1 thread) · "
          f"train-procRSS={o['training_process_peak_rss_mb']:.0f} MB"
          + (f" · int8={o.get('int8_bytes',0)/1024:.1f} KB" if "int8_bytes" in o else ""))
    return rep


if __name__ == "__main__":
    raise SystemExit(main())
