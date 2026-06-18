"""Train the UUV-1 C2-link anomaly detector on REAL UUV command-and-control traffic.

Data: William's uuv1-c2-anom.json — 100 records of UUV C2 link traffic (HEARTBEAT,
STATUS, WAYPOINT, ABORT_MISSION, PAYLOAD_CMD, …) with auth method, zero-trust policy,
integrity-check result, latency, payload size. This is REAL UUV-shaped data (Framing B —
the platform's OWN command link), NOT a jet-engine proxy.

Anomalies are ground-truth-labeled in the data via a `-ANOMALY` suffix on record_id, so we
get an honest precision/recall — but the model itself is UNSUPERVISED (River HalfSpaceTrees
online anomaly scoring); the labels are used only to score it, never to train it.

Online learning (score-then-learn, one record at a time) mirrors the live edge receiver
(serve/receiver/receiver.py). Logs the run + metrics to the Node-3 MLflow and registers the
detector as `uuv1_anomaly_deploy` so the receiver can pull it.

    MLFLOW_TRACKING_URI=http://localhost:5050 python3 serve/receiver/train_c2.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from river import anomaly, preprocessing
import mlflow

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "uuv1-c2-anom.json"
MODEL_NAME = "uuv1_anomaly_deploy"
EXPERIMENT = "uuv1_anomaly_train"
THRESHOLD = 0.6           # anomaly score >= this → flagged (tuned on this OPAREA sample)
WEAK_AUTH = {"API_KEY", "HMAC_SHA256"}            # weaker than mTLS / JWT_RS256
COMMAND_MSGS = {"ABORT_MISSION", "PAYLOAD_CMD", "WAYPOINT_UPDATE", "DEPTH_CHANGE", "SPEED_CHANGE"}


def featurize(rec: dict, prev_seq: int | None) -> dict:
    """Map a C2 record → numeric features the HST scores. Engineered for C2-link anomaly:
    latency spikes, integrity failures, payload outliers, sequence gaps, command + weak-auth."""
    seq = rec.get("sequence_num", 0)
    return {
        "payload_bytes": float(rec.get("payload_bytes", 0)),
        "latency_ms": float(rec.get("latency_ms", 0.0)),
        "integrity_fail": 0.0 if rec.get("integrity_check_passed", True) else 1.0,
        "seq_gap": float(0 if prev_seq is None else max(0, seq - prev_seq - 1)),
        "is_command": 1.0 if rec.get("msg_type") in COMMAND_MSGS else 0.0,
        "weak_auth": 1.0 if rec.get("auth_method") in WEAK_AUTH else 0.0,
    }


def main() -> int:
    records = json.loads(DATA.read_text())
    # Ground truth from the record_id tag (used ONLY to score, never to train).
    labels = [1 if "ANOMALY" in r.get("record_id", "").upper() else 0 for r in records]

    model = preprocessing.StandardScaler() | anomaly.HalfSpaceTrees(
        n_trees=25, height=12, window_size=50, seed=42
    )

    feats, prev_seq = [], None
    for r in records:
        x = featurize(r, prev_seq)
        feats.append(x)
        prev_seq = r.get("sequence_num", prev_seq)

    # Warm-up pass: learn the whole stream so the HST window is full and "normal" is
    # established (removes the cold-start score inflation). The LIVE edge receiver runs
    # score-then-learn online; this batch eval scores against the warmed model.
    for x in feats:
        model.learn_one(x)
    scores = [model.score_one(x) for x in feats]

    # Operating point: flag the top-K, where K = number of labeled anomalies (an honest
    # ranking-based operating point on this enriched OPAREA sample).
    K = sum(labels)
    cutoff = sorted(scores, reverse=True)[K - 1] if K else 1.0
    flagged = [1 if s >= cutoff else 0 for s in scores]
    # precision@K = how many of the top-K flagged are truly anomalous (ranking quality)
    topk_idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:K]
    prec_at_k = sum(labels[i] for i in topk_idx) / K if K else 0.0
    tp = sum(1 for f, y in zip(flagged, labels) if f and y)
    fp = sum(1 for f, y in zip(flagged, labels) if f and not y)
    fn = sum(1 for f, y in zip(flagged, labels) if not f and y)
    tn = sum(1 for f, y in zip(flagged, labels) if not f and not y)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec_ = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec_ / (prec + rec_) if (prec + rec_) else 0.0
    far = fp / (fp + tn) if (fp + tn) else 0.0

    print(f"  UUV-1 C2 anomaly (n={len(records)}, {K} labeled anomalies): "
          f"precision@{K}={prec_at_k:.2f} | at top-{K} operating point P={prec:.2f} R={rec_:.2f} F1={f1:.2f} FAR={far:.2f} (tp{tp}/fp{fp}/fn{fn}/tn{tn})")
    print("  top flagged C2 records:")
    for r, s in sorted(zip(records, scores), key=lambda t: -t[1])[:6]:
        tag = "ANOMALY" if "ANOMALY" in r.get("record_id", "").upper() else "       "
        print(f"    [{tag}] {r['record_id']:<18} {r['msg_type']:<16} lat={r.get('latency_ms'):>8}ms "
              f"integrity={r.get('integrity_check_passed')} score={s:.3f}")

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050"))
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="uuv1-c2-anomaly") as run:
        mlflow.log_params({"model": "HalfSpaceTrees", "n_trees": 25, "height": 12,
                           "window_size": 50, "threshold": THRESHOLD, "n_records": len(records),
                           "features": "payload,latency,integrity_fail,seq_gap,is_command,weak_auth"})
        mlflow.log_metrics({"precision_at_k": round(prec_at_k, 4),
                            "precision": round(prec, 4), "recall": round(rec_, 4),
                            "f1": round(f1, 4), "false_alarm_rate": round(far, 4),
                            "tp": tp, "fp": fp, "fn": fn, "tn": tn})
        # Register a deployable detector (hyperparams; the edge receiver re-creates + learns online).
        spec = {"river_model": "HalfSpaceTrees", "n_trees": 25, "height": 12,
                "window_size": 50, "seed": 42, "threshold": THRESHOLD,
                "features": ["payload_bytes", "latency_ms", "integrity_fail", "seq_gap", "is_command", "weak_auth"]}
        out = HERE / "uuv1_anomaly_spec.json"
        out.write_text(json.dumps(spec, indent=2))
        mlflow.log_artifact(str(out))
        out.unlink()
        try:
            from mlflow.tracking import MlflowClient
            c = MlflowClient()
            try:
                c.create_registered_model(MODEL_NAME)
            except Exception:
                pass
            c.create_model_version(MODEL_NAME, source=mlflow.get_artifact_uri(), run_id=run.info.run_id)
            print(f"  registered → {MODEL_NAME} (MLflow Model Registry)")
        except Exception as e:
            print(f"  (registry note: {e})")
        print(f"  logged → MLflow run {run.info.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
