#!/usr/bin/env python3
"""THESEUS — UUV own-systems sequence autoencoder (`theseus-uuv`), Pi-5-4GB deployable.

The honest Framing-B model: an UNSUPERVISED sequence autoencoder over REAL underwater-vehicle
subsystem telemetry (BlueROV2 / ArduSub — battery, thrusters, attitude, IMU, pressure), NOT a
gas-turbine/turbofan proxy. Trains on NOMINAL windows only (cold-start, no anomaly labels at
train time), scores per-window reconstruction error, thresholds at a target false-alarm rate,
then exports to ONNX (+int8) with a single-thread Pi resource benchmark and registers in MLflow
as `theseus-uuv` (the fleet contract in fleet/mlflow_registry.py).

Architecture: length-preserving 1D-Conv autoencoder with a Linear bottleneck
  enc: Conv1d(C,32,k5) - Conv1d(32,16,k5) - Flatten - Linear(16*W, latent)
  dec: Linear(latent, 16*W) - Conv1d(16,32,k5) - Conv1d(32,C,k5)
(Conv1d/Linear export cleanly to ONNX, unlike LSTM/GRU; int8 dynamic-quant accelerates the
Linear bottleneck MatMuls — a real win here, unlike the NV063 tree ensemble where int8 was a no-op.)

HONESTY (non-negotiable, matches eval/RESULTS.md tone):
  * Data is REAL BlueROV2 telemetry (Zenodo 10.5281/zenodo.17360027, CC BY 4.0) but all NOMINAL —
    there is NO public fault-labeled BlueROV2 set. So anomaly eval uses SYNTHETIC fault injection
    (thruster dropout/stuck, battery sag, attitude drift, IMU spike, internal-pressure "leak")
    applied to held-out nominal windows. These are SYNTHETIC perturbations for threshold
    calibration + separability illustration — NOT real failures. Numbers are illustrative.
  * Recording-level split (train/val/test by recording) — no window leakage across split.
  * Standardization fit on TRAIN windows only.

  python3 models/uuv/train_uuv_ae.py [--window 64] [--epochs 60] [--latent 32] [--target-far 0.02]

Writes:
  models/uuv/model.pt        torch state_dict
  models/uuv/scaler.json     per-channel mean/std + channel order + window + threshold
  models/uuv/meta.json       arch/params/sha256
  models/uuv/results.json    honest eval (nominal vs each synthetic fault) + edge benchmark
  models/onnx/uuv_seq_ae.onnx (+ _int8.onnx)   edge artifacts
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "ingest" / "out" / "ardusub.csv"
ONNX_DIR = ROOT / "models" / "onnx"
SEED = 316


# ----------------------------------------------------------------------------- data
def load_recordings(path: Path):
    """Return {recording: ndarray(T, C)} and the channel name list (order preserved)."""
    rows = defaultdict(list)
    with path.open() as f:
        rdr = csv.reader(f)
        header = next(rdr)
        chans = header[2:]  # skip recording, t
        for r in rdr:
            rows[r[0]].append([float(x) for x in r[2:]])
    return {k: np.asarray(v, dtype=np.float64) for k, v in rows.items()}, chans


def make_windows(arr: np.ndarray, W: int, stride: int) -> np.ndarray:
    """(T, C) -> (n_win, C, W) windows formed WITHIN one recording (no cross-boundary)."""
    T = arr.shape[0]
    if T < W:
        return np.empty((0, arr.shape[1], W), dtype=np.float32)
    idx = range(0, T - W + 1, stride)
    return np.stack([arr[i:i + W].T for i in idx]).astype(np.float32)  # (n, C, W)


# ----------------------------------------------------------- synthetic fault injection (eval only)
def inject_fault(win: np.ndarray, kind: str, ch: dict, rng: np.random.Generator) -> np.ndarray:
    """Apply one SYNTHETIC fault to a standardized nominal window (C, W). Eval-only — clearly
    synthetic, NOT a real failure. Perturbations are physically-motivated per subsystem."""
    w = win.copy()
    C, W = w.shape
    if kind == "thruster_dropout":               # a thruster output collapses to ~0 mid-window
        t = rng.integers(ch["thr1"], ch["thr6"] + 1)
        w[t, W // 2:] = (0.0 - 0.0)               # standardized -> drive toward the channel mean shift
        w[t, W // 2:] -= 3.0
    elif kind == "thruster_stuck":                # a thruster saturates high and stops responding
        t = rng.integers(ch["thr1"], ch["thr6"] + 1)
        w[t, :] = 3.0
    elif kind == "battery_sag":                   # voltage ramps down across the window
        w[ch["batt_voltage"]] += np.linspace(0, -4.0, W)
    elif kind == "attitude_drift":                # roll/pitch bias (lost trim / entanglement)
        w[ch["att_roll"]] += np.linspace(0, 3.0, W)
        w[ch["att_pitch"]] += np.linspace(0, 2.0, W)
    elif kind == "imu_spike":                      # transient accel/gyro spikes (knock / fouling)
        a = rng.integers(ch["imu_xacc"], ch["imu_zgyro"] + 1)
        for _ in range(max(2, W // 16)):
            w[a, rng.integers(0, W)] += rng.choice([-1, 1]) * 5.0
    elif kind == "pressure_leak":                  # internal pressure rises (water ingress)
        w[ch["press_int"]] += np.linspace(0, 4.0, W)
    else:
        raise ValueError(kind)
    return w


FAULTS = ["thruster_dropout", "thruster_stuck", "battery_sag",
          "attitude_drift", "imu_spike", "pressure_leak"]


# ----------------------------------------------------------------------------- metrics
def metrics(y, score, thr):
    """precision/recall/false_alarm/f1 at threshold `thr` (eval/score.py defs) + ROC-AUC."""
    from sklearn.metrics import roc_auc_score
    yhat = [1 if s > thr else 0 for s in score]
    tp = sum(1 for a, b in zip(y, yhat) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y, yhat) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y, yhat) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(y, yhat) if a == 0 and b == 0)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    far = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    auc = float(roc_auc_score(y, score)) if 0 < sum(y) < len(y) else None
    return {"precision": round(prec, 4), "recall": round(rec, 4),
            "false_alarm_rate": round(far, 4), "f1": round(f1, 4),
            "roc_auc": round(auc, 4) if auc is not None else None,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


# ----------------------------------------------------------------------------- model
def build_model(C: int, W: int, latent: int):
    import torch.nn as nn

    class ConvAE(nn.Module):
        def __init__(self):
            super().__init__()
            self.W = W
            self.enc = nn.Sequential(
                nn.Conv1d(C, 32, 5, padding=2), nn.ReLU(),
                nn.Conv1d(32, 16, 5, padding=2), nn.ReLU(),
            )
            self.to_latent = nn.Linear(16 * W, latent)
            self.from_latent = nn.Linear(latent, 16 * W)
            self.dec = nn.Sequential(
                nn.Conv1d(16, 32, 5, padding=2), nn.ReLU(),
                nn.Conv1d(32, C, 5, padding=2),
            )

        def forward(self, x):                      # x: (B, C, W)
            z = self.enc(x).flatten(1)
            z = self.to_latent(z)
            h = self.from_latent(z).reshape(-1, 16, self.W)
            return self.dec(h)

    return ConvAE()


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Train the UUV own-systems sequence autoencoder.")
    ap.add_argument("--window", type=int, default=64, help="window length in samples (~6.4 s @10 Hz)")
    ap.add_argument("--stride", type=int, default=8, help="train window stride")
    ap.add_argument("--latent", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--target-far", type=float, default=0.02,
                    help="threshold set at this false-alarm rate on nominal validation")
    a = ap.parse_args()
    if not DATA.exists():
        print(f"  telemetry missing: {DATA} (run `python3 ingest/ardusub.py`)"); return 1

    import torch
    import torch.nn as nn
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    print("THESEUS · UUV own-systems sequence autoencoder (theseus-uuv)")
    recs, chans = load_recordings(DATA)
    C = len(chans)
    ch_idx = {c: i for i, c in enumerate(chans)}
    W = a.window

    # ---- recording-level split (no window leakage) ----
    rec_ids = sorted(recs)
    rng.shuffle(rec_ids)
    n = len(rec_ids)
    n_tr, n_val = max(1, int(n * 0.7)), max(1, int(n * 0.15))
    tr_recs = rec_ids[:n_tr]
    val_recs = rec_ids[n_tr:n_tr + n_val]
    te_recs = rec_ids[n_tr + n_val:]
    print(f"  {n} recordings -> train {len(tr_recs)} / val {len(val_recs)} / test {len(te_recs)} "
          f"· {C} channels · window {W} ({W/10:.1f}s @10Hz)")

    # ---- standardize on TRAIN windows only ----
    Xtr_raw = np.concatenate([make_windows(recs[r], W, a.stride) for r in tr_recs])  # (n,C,W)
    mean = Xtr_raw.mean(axis=(0, 2))                       # per-channel
    std = Xtr_raw.std(axis=(0, 2))
    std[std < 1e-6] = 1.0                                  # guard constant channels (e.g. idle thrusters)

    def standardize(w):                                    # w: (...,C,W)
        return (w - mean[:, None]) / std[:, None]

    vstride = max(1, W // 4)   # finer stride on val/test -> more windows -> stable threshold + eval
    Xtr = standardize(Xtr_raw)
    Xval = standardize(np.concatenate([make_windows(recs[r], W, vstride) for r in val_recs]))
    Xte_nom = standardize(np.concatenate([make_windows(recs[r], W, vstride) for r in te_recs]))
    print(f"  windows: train {len(Xtr):,} · val {len(Xval):,} · test-nominal {len(Xte_nom):,}")

    # ---- train AE on nominal windows ----
    model = build_model(C, W, a.latent)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs)
    lossf = nn.MSELoss()
    Xtr_t = torch.tensor(Xtr)
    bs = 256
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        perm = torch.randperm(len(Xtr_t))
        ep_loss = 0.0
        for i in range(0, len(Xtr_t), bs):
            b = Xtr_t[perm[i:i + bs]]
            opt.zero_grad()
            loss = lossf(model(b), b)
            loss.backward(); opt.step()
            ep_loss += loss.item() * len(b)
        sched.step()
        if ep % 25 == 0 or ep == a.epochs - 1:
            print(f"  epoch {ep:3d}  train_recon_mse={ep_loss/len(Xtr_t):.5f}")
    fit_s = time.time() - t0

    # ---- per-window reconstruction error ----
    model.eval()

    def recon_err(X):
        with torch.no_grad():
            xt = torch.tensor(X.astype(np.float32))
            e = ((model(xt) - xt) ** 2).mean(dim=(1, 2)).numpy()
        return e

    # shipped default threshold = target-FAR quantile on pooled nominal validation (a starting point;
    # deployment re-calibrates in-situ — see eval below).
    thr = float(np.quantile(recon_err(Xval), 1 - a.target_far))
    print(f"  shipped default threshold@far~{a.target_far}: {thr:.5f} (re-calibrate in-situ on deploy)")

    # ---- honest eval: per-recording IN-SITU threshold (mirrors cold-start deployment) ----
    # A fielded UUV has no labels and no fleet baseline at cold-start; it learns ITS OWN nominal
    # envelope in-situ (the same story as demo/ais_pol.py). So for each held-out TEST recording we
    # calibrate the threshold on the FIRST HALF of its nominal windows, then evaluate on the SECOND
    # HALF (nominal, label 0) + synthetic faults injected into those (label 1). AUC is threshold-free
    # (pooled across recordings); P/R/FAR/F1 are at the per-recording in-situ operating point.
    from sklearn.metrics import roc_auc_score
    acc = {fk: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for fk in FAULTS}
    pool = {fk: {"y": [], "s": []} for fk in FAULTS}
    thr_used = []
    n_eval_nom = 0   # total held-out nominal eval windows across ALL test recordings (not just the last)
    for r in te_recs:
        Xr = standardize(make_windows(recs[r], W, vstride))
        if len(Xr) < 8:
            continue
        half = len(Xr) // 2
        thr_r = float(np.quantile(recon_err(Xr[:half]), 1 - a.target_far))  # in-situ calibration
        thr_used.append(thr_r)
        ev = Xr[half:]
        err_nom = recon_err(ev)
        n_eval_nom += len(err_nom)
        for fk in FAULTS:
            err_f = recon_err(np.stack([inject_fault(w, fk, ch_idx, rng) for w in ev]))
            for e in err_nom:
                acc[fk]["fp" if e > thr_r else "tn"] += 1
            for e in err_f:
                acc[fk]["tp" if e > thr_r else "fn"] += 1
            pool[fk]["y"] += [0] * len(err_nom) + [1] * len(err_f)
            pool[fk]["s"] += list(err_nom) + list(err_f)

    def _op(c):
        prec = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else 0.0
        rec = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else 0.0
        far = c["fp"] / (c["fp"] + c["tn"]) if (c["fp"] + c["tn"]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        return prec, rec, far, f1

    per_fault, allc, ally, alls = {}, {"tp": 0, "fp": 0, "fn": 0, "tn": 0}, [], []
    for fk in FAULTS:
        c = acc[fk]
        prec, rec, far, f1 = _op(c)
        auc = round(float(roc_auc_score(pool[fk]["y"], pool[fk]["s"])), 4)
        per_fault[fk] = {"precision": round(prec, 4), "recall": round(rec, 4),
                         "false_alarm_rate": round(far, 4), "f1": round(f1, 4), "roc_auc": auc, **c}
        for k in allc:
            allc[k] += c[k]
        ally += pool[fk]["y"]; alls += pool[fk]["s"]
        print(f"    {fk:18s} AUC={auc} P={round(prec,3)} R={round(rec,3)} "
              f"FAR={round(far,3)} F1={round(f1,3)}")
    oprec, orec, ofar, of1 = _op(allc)
    overall = {"precision": round(oprec, 4), "recall": round(orec, 4),
               "false_alarm_rate": round(ofar, 4), "f1": round(of1, 4),
               "roc_auc": round(float(roc_auc_score(ally, alls)), 4), **allc}
    thr_insitu = round(float(np.mean(thr_used)), 5) if thr_used else thr
    print(f"  in-situ thresholds (mean over {len(thr_used)} test recordings): {thr_insitu}")
    print(f"  OVERALL (all synthetic faults): AUC={overall['roc_auc']} P={overall['precision']} "
          f"R={overall['recall']} FAR={overall['false_alarm_rate']} F1={overall['f1']}")

    # ---- persist torch model + scaler + meta ----
    HERE.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), HERE / "model.pt")
    model_sha = hashlib.sha256((HERE / "model.pt").read_bytes()).hexdigest()
    scaler = {"channels": chans, "mean": mean.tolist(), "std": std.tolist(),
              "window": W, "latent": a.latent, "threshold": thr, "target_far": a.target_far}
    (HERE / "scaler.json").write_text(json.dumps(scaler, indent=2))
    meta = {"name": "theseus-uuv", "model": "Conv1d sequence autoencoder", "framework": "pytorch",
            "kind": "sequence-autoencoder-anomaly", "channels": C, "window": W, "latent": a.latent,
            "arch": f"Conv1d({C},32,16)->Linear(->{a.latent}->)->Conv1d(16,32,{C})",
            "epochs": a.epochs, "n_train_windows": len(Xtr), "seed": SEED,
            "model_sha256": model_sha, "trained_unix": time.time()}
    (HERE / "meta.json").write_text(json.dumps(meta, indent=2))

    # ---- ONNX export (+int8) + Pi single-thread benchmark ----
    edge = export_and_bench(model, Xte_nom, recon_err, C, W)

    results = {
        "dataset": "BlueROV2 ROV tether dataset (Zenodo 10.5281/zenodo.17360027, CC BY 4.0) — "
                   "REAL ArduSub onboard telemetry; ONBOARD channels only (mocap/pose/tension excluded).",
        "framing": "B — the UUV's OWN subsystems (battery/thrusters/attitude/IMU/pressure). Real "
                   "underwater-vehicle data, NOT a gas-turbine/turbofan proxy.",
        "channels": chans, "n_channels": C, "window": W, "rate_hz": 10,
        "split": {"train_recordings": tr_recs, "val_recordings": val_recs, "test_recordings": te_recs},
        "n_train_windows": len(Xtr), "n_val_windows": len(Xval), "n_test_nominal_windows": n_eval_nom,
        "shipped_default_threshold": round(thr, 6), "insitu_threshold_mean": thr_insitu,
        "target_far": a.target_far, "fit_seconds": round(fit_s, 2),
        "eval_method": "per-recording IN-SITU threshold (calibrate on first half of each held-out "
                       "test recording's nominal windows, evaluate on second half + synthetic faults) "
                       "— mirrors cold-start deployment. AUC pooled across recordings (threshold-free).",
        "eval_per_synthetic_fault": per_fault,
        "eval_overall_synthetic": overall,
        "edge": edge,
        "caveats": "Data is REAL but ALL NOMINAL (no public fault-labeled BlueROV2 set). Anomaly "
                   "eval uses SYNTHETIC fault injection on held-out nominal windows (thruster "
                   "dropout/stuck, battery sag, attitude drift, IMU spike, internal-pressure leak) "
                   "— SYNTHETIC perturbations for separability illustration + in-situ threshold "
                   "calibration, NOT real failures. ROC-AUC is threshold-free separability; P/R/FAR/F1 "
                   "at the per-recording in-situ operating point. n is illustrative. Validate on "
                   "self-captured BlueROV2 fault runs before any claim of fielded detection performance.",
    }
    (HERE / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"  wrote models/uuv/{{model.pt, scaler.json, meta.json, results.json}} "
          f"(sha256={model_sha[:12]}…)")

    # ---- MLflow registry: register as theseus-uuv (no-op if MLflow unavailable) ----
    register_theseus_uuv(overall, per_fault, edge, a)
    return 0


def export_and_bench(model, Xte_nom, recon_err, C, W) -> dict:
    """torch.onnx export (+int8 dynamic quant) + single-thread Pi parity/latency/RSS bench."""
    import torch
    rep: dict = {"onnx": None}
    try:
        import onnxruntime as ort
    except ImportError as e:
        rep["error"] = f"onnx bench skipped (missing dep): {e}"; return rep

    ONNX_DIR.mkdir(parents=True, exist_ok=True)
    fp32 = ONNX_DIR / "uuv_seq_ae.onnx"
    int8 = ONNX_DIR / "uuv_seq_ae_int8.onnx"
    dummy = torch.zeros(1, C, W, dtype=torch.float32)
    model.eval()
    try:
        torch.onnx.export(model, dummy, fp32.as_posix(), input_names=["window"],
                          output_names=["recon"], opset_version=17, dynamo=False)
    except Exception as e:
        rep["error"] = f"torch.onnx.export failed: {e}"; print(f"  [onnx] export failed: {e}"); return rep

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1          # mimic a single Pi core
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(fp32.as_posix(), so, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    # parity: torch recon-error vs onnx recon-error on test-nominal windows
    n_par = min(256, len(Xte_nom))
    Xp = Xte_nom[:n_par].astype(np.float32)
    with torch.no_grad():
        torch_recon = model(torch.tensor(Xp)).numpy()
    onnx_recon = np.concatenate([sess.run(None, {in_name: Xp[i:i+1]})[0] for i in range(n_par)])
    max_abs = float(np.max(np.abs(torch_recon - onnx_recon)))
    torch_err = ((torch_recon - Xp) ** 2).mean(axis=(1, 2))
    onnx_err = ((onnx_recon - Xp) ** 2).mean(axis=(1, 2))
    err_max_abs = float(np.max(np.abs(torch_err - onnx_err)))

    # single-window latency (the onboard per-call cost), 1 thread
    one = Xp[:1]
    for _ in range(20):
        sess.run(None, {in_name: one})
    t = time.time(); N = 500
    for _ in range(N):
        sess.run(None, {in_name: one})
    lat_ms = (time.time() - t) / N * 1000
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)  # macOS bytes

    rep["onnx"] = {
        "fp32_path": str(fp32.relative_to(ROOT)), "fp32_kb": round(fp32.stat().st_size / 1024, 1),
        "torch_vs_onnx_recon_max_abs": round(max_abs, 8),
        "torch_vs_onnx_recon_err_max_abs": round(err_max_abs, 10),
        "single_window_latency_ms_1thread": round(lat_ms, 4),
        "training_process_peak_rss_mb": round(peak_rss_mb, 1),
        "rss_note": "full TRAINING process RSS (torch+numpy+onnxruntime); honest inference-only "
                    "footprint is in models/uuv/pi_bench.json.",
    }
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
        quantize_dynamic(fp32.as_posix(), int8.as_posix(), weight_type=QuantType.QInt8)
        rep["onnx"]["int8_path"] = str(int8.relative_to(ROOT))
        rep["onnx"]["int8_kb"] = round(int8.stat().st_size / 1024, 1)
        rep["onnx"]["int8_note"] = ("dynamic quant targets MatMul/Gemm -> shrinks the Linear "
                                    "bottleneck (the bulk of params); Conv1d stays fp32 under "
                                    "dynamic quant (static quant would cover it). Unlike NV063's "
                                    "tree ensemble, int8 gives a real size reduction here.")
    except Exception as e:
        rep["onnx"]["int8_note"] = f"int8 quant skipped/limited: {e}"

    o = rep["onnx"]
    print(f"  [onnx] fp32={o['fp32_kb']:.1f} KB"
          + (f" · int8={o.get('int8_kb',0):.1f} KB" if "int8_kb" in o else "")
          + f" · recon parity max|Δ|={o['torch_vs_onnx_recon_max_abs']:.2e}"
          + f" · {o['single_window_latency_ms_1thread']:.3f} ms/window (1 thread)")
    return rep


def register_theseus_uuv(overall, per_fault, edge, args) -> None:
    """Register the ONNX artifact as `theseus-uuv` in the MLflow fleet registry (no-op if
    MLflow unavailable, per fleet/mlflow_registry.py). Also direct-logs params/metrics."""
    import sys
    sys.path.insert(0, str(ROOT / "fleet"))
    try:
        import mlflow_registry as reg
    except Exception as e:
        print(f"  (mlflow registry glue import failed: {e})"); return
    onnx_path = ROOT / (edge.get("onnx", {}) or {}).get("int8_path", "") if edge.get("onnx") else None
    metrics = {f"auc_{k}": (v["roc_auc"] or 0.0) for k, v in per_fault.items()}
    metrics.update({"overall_auc": overall["roc_auc"] or 0.0, "overall_f1": overall["f1"],
                    "overall_far": overall["false_alarm_rate"],
                    "fp32_kb": (edge.get("onnx") or {}).get("fp32_kb", 0.0),
                    "int8_kb": (edge.get("onnx") or {}).get("int8_kb", 0.0)})
    ok = reg.log_fleet_round(metrics, onnx_path, run_name="theseus-uuv-seq-ae")
    if ok:
        print(f"  registered model in MLflow fleet registry as '{reg.MODEL_NAME}'")
    else:
        print(f"  (MLflow unavailable — set MLFLOW_TRACKING_URI to register as '{reg.MODEL_NAME}'; "
              f"local artifacts in models/uuv/ + models/onnx/ stand)")


if __name__ == "__main__":
    raise SystemExit(main())
