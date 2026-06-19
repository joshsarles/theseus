#!/usr/bin/env python3
"""THESEUS — independent test harness for the deployed `theseus-uuv` model.

Tests the ARTIFACT WE WOULD SHIP (the ONNX model + saved scaler), not the in-process torch
model, on the held-out TEST recordings from the training split (read from results.json — no
re-fit, no leakage). Reports an HONEST battery of checks (hardened after an adversarial audit):

  1. CONSISTENCY  — shipped ONNX vs trained torch reconstruction error agree (deploy == train)
  2. NOMINAL      — reconstruction-error distribution on held-out healthy windows (+ per recording)
  3. SEVERITY     — detection vs synthetic-fault magnitude (controlled: same fault realization scaled)
  4. SEPARABILITY — per-recording ROC-AUC (deployment-relevant) + pooled + a TRIVIAL no-model baseline
  5. LOCALIZATION — per-channel error increase, NORMALIZED by each channel's nominal error (sanity check)
  6. OPERATING    — ROC + (FAR, recall) across thresholds (nominal pooled once)

Audit-driven honesty fixes vs the first version:
  * Detection is evaluated on the DISJOINT second half of each recording; the in-situ threshold is
    calibrated on the first half only (matches the trainer; removes calib/eval window reuse).
  * Severity sweep scales ONE fault realization (precomputed) so x0.25..x4 perturb the SAME channels
    (a true controlled magnitude sweep, not a different random thruster per scale).
  * Reports PER-RECORDING AUC (the deployment number) — the pooled AUC is dragged down ~0.1 by the
    ~9x cross-recording nominal-error scale gap and is NOT the headline.
  * Reports a TRIVIAL no-model baseline (mean-squared standardized value) so the model's marginal
    lift is visible.
  * Localization is normalized by each channel's nominal recon-MSE (so the worst-reconstructed
    channel, temp_int, doesn't falsely co-lead) and is labeled a SANITY CHECK, not diagnosis.

  python3 models/uuv/test_uuv_ae.py [--int8]

Writes models/uuv/test_report.json. Eval-only. HONESTY: faults are SYNTHETIC perturbations of
held-out REAL nominal data — illustrative, not real failures.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from train_uuv_ae import load_recordings, make_windows, inject_fault, FAULTS  # noqa: E402

DATA = ROOT / "ingest" / "out" / "ardusub.csv"


def main() -> int:
    ap = argparse.ArgumentParser(description="Independent test of the deployed theseus-uuv model.")
    ap.add_argument("--int8", action="store_true", help="test the int8 ONNX instead of fp32")
    a = ap.parse_args()

    import onnxruntime as ort
    from sklearn.metrics import roc_auc_score

    for p in (DATA, HERE / "scaler.json", HERE / "results.json", HERE / "meta.json"):
        if not p.exists():
            print(f"  missing: {p} (run ingest/ardusub.py + train_uuv_ae.py first)"); return 1

    sc = json.loads((HERE / "scaler.json").read_text())
    res = json.loads((HERE / "results.json").read_text())
    chans, mean, std = sc["channels"], np.array(sc["mean"]), np.array(sc["std"])
    W, ship_thr, target_far = sc["window"], sc["threshold"], sc["target_far"]
    C = len(chans)
    ch_idx = {c: i for i, c in enumerate(chans)}
    te_recs = res["split"]["test_recordings"]    # exact held-out recordings (no leakage)
    rng = np.random.default_rng(2025)

    onnx_name = "uuv_seq_ae_int8.onnx" if a.int8 else "uuv_seq_ae.onnx"
    model_path = ROOT / "models" / "onnx" / onnx_name
    so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1
    sess = ort.InferenceSession(model_path.as_posix(), so, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    def standardize(w):
        return (w - mean[:, None]) / np.where(std < 1e-6, 1.0, std)[:, None]

    def onnx_recon(X):
        return np.concatenate([sess.run(None, {in_name: X[i:i+1].astype(np.float32)})[0]
                               for i in range(len(X))]) if len(X) else np.empty((0, C, W))

    def err_of(X):
        if not len(X):
            return np.empty(0)
        r = onnx_recon(X)
        return ((r - X) ** 2).mean(axis=(1, 2))

    def trivial_score(X):                          # no-model baseline: mean squared standardized value
        return (X ** 2).mean(axis=(1, 2)) if len(X) else np.empty(0)

    print(f"THESEUS · independent test of deployed theseus-uuv ({onnx_name})")
    print(f"  held-out TEST recordings: {te_recs}")
    recs, _ = load_recordings(DATA)

    nom = {r: standardize(make_windows(recs[r], W, max(1, W // 4))) for r in te_recs}
    Xnom_all = np.concatenate([v for v in nom.values()])
    report: dict = {"model": str(model_path.relative_to(ROOT)), "precision": "int8" if a.int8 else "fp32",
                    "test_recordings": te_recs, "n_nominal_windows_total": int(len(Xnom_all))}

    # ---- 1. CONSISTENCY: shipped ONNX vs trained torch ----
    import torch
    from train_uuv_ae import build_model
    m = build_model(C, W, sc["latent"]); m.load_state_dict(torch.load(HERE / "model.pt")); m.eval()
    with torch.no_grad():
        tr = m(torch.tensor(Xnom_all.astype(np.float32))).numpy()
    torch_err = ((tr - Xnom_all) ** 2).mean(axis=(1, 2))
    onnx_err_all = err_of(Xnom_all)
    cons = {"recon_err_max_abs_diff": float(np.max(np.abs(torch_err - onnx_err_all))),
            "recon_err_corr": float(np.corrcoef(torch_err, onnx_err_all)[0, 1])}
    report["consistency_onnx_vs_torch"] = cons
    print(f"\n[1] CONSISTENCY  shipped-ONNX vs trained-torch recon-err: "
          f"max|Δ|={cons['recon_err_max_abs_diff']:.2e}  corr={cons['recon_err_corr']:.5f}")

    # ---- 2. NOMINAL distribution (full nominal, per recording) ----
    per_rec = {r: {"n": int(len(nom[r])), "mean": round(float(err_of(nom[r]).mean()), 4),
                   "p98": round(float(np.quantile(err_of(nom[r]), 0.98)), 4)} for r in te_recs}
    report["nominal"] = {"mean_all": round(float(onnx_err_all.mean()), 4),
                         "shipped_threshold": ship_thr, "per_recording": per_rec,
                         "scale_spread_ratio": round(max(v["mean"] for v in per_rec.values())
                                                     / max(1e-9, min(v["mean"] for v in per_rec.values())), 1)}
    print(f"[2] NOMINAL      recon-err mean(all)={onnx_err_all.mean():.4f}  (shipped thr={ship_thr:.4f})")
    for r in te_recs:
        print(f"       {r:20s} mean={per_rec[r]['mean']:.4f} p98={per_rec[r]['p98']:.4f} n={per_rec[r]['n']}")
    print(f"       -> cross-recording nominal-error scale spread: {report['nominal']['scale_spread_ratio']}x")

    # ---- disjoint halves: calibrate in-situ threshold on first half, evaluate on second half ----
    evalh, calib_thr, faulted = {}, {}, {}
    for r in te_recs:
        if len(nom[r]) < 8:
            continue
        half = len(nom[r]) // 2
        calib_thr[r] = float(np.quantile(err_of(nom[r][:half]), 1 - target_far))
        evalh[r] = nom[r][half:]
        faulted[r] = {fk: np.stack([inject_fault(w, fk, ch_idx, rng) for w in evalh[r]]) for fk in FAULTS}

    # ---- 3. SEVERITY sweep (controlled: scale the SAME precomputed fault realization) ----
    scales = [0.25, 0.5, 1.0, 2.0, 4.0]
    severity = {fk: {} for fk in FAULTS}
    for fk in FAULTS:
        for s in scales:
            ys, ss, tp, tot = [], [], 0, 0
            for r in evalh:
                ev = evalh[r]
                scaled = ev + s * (faulted[r][fk] - ev)   # s=1 == training-strength fault, same channels
                ef, en = err_of(scaled), err_of(ev)
                ys += [0]*len(en) + [1]*len(ef); ss += list(en) + list(ef)
                tp += int((ef > calib_thr[r]).sum()); tot += len(ef)
            severity[fk][f"x{s}"] = {"auc": round(float(roc_auc_score(ys, ss)), 3),
                                     "recall_insitu": round(tp / tot, 3) if tot else None}
    report["severity_sweep"] = {"scales": scales, "by_fault": severity}
    print(f"\n[3] SEVERITY sweep — recall at in-situ threshold (AUC), fault strength x{scales}:")
    for fk in FAULTS:
        print(f"       {fk:18s} " + "  ".join(
            f"{severity[fk][f'x{s}']['recall_insitu']:.2f}({severity[fk][f'x{s}']['auc']:.2f})" for s in scales))

    # ---- 4. SEPARABILITY: per-recording AUC (deployment) + pooled + trivial no-model baseline ----
    per_rec_auc, pool_y, pool_s, pool_triv = {}, [], [], []
    for r in evalh:
        ev = evalh[r]
        y = [0]*len(ev) + [1]*len(ev)*len(FAULTS)
        s_model = list(err_of(ev)) + [v for fk in FAULTS for v in err_of(faulted[r][fk])]
        s_triv = list(trivial_score(ev)) + [v for fk in FAULTS for v in trivial_score(faulted[r][fk])]
        per_rec_auc[r] = round(float(roc_auc_score(y, s_model)), 3)
        pool_y += y; pool_s += s_model; pool_triv += s_triv
    aucs = sorted(per_rec_auc.values())
    sep = {"per_recording_auc": per_rec_auc,
           "per_recording_auc_median": float(np.median(aucs)),
           "per_recording_auc_range": [min(aucs), max(aucs)],
           "pooled_auc": round(float(roc_auc_score(pool_y, pool_s)), 4),
           "trivial_baseline_pooled_auc": round(float(roc_auc_score(pool_y, pool_triv)), 4)}
    sep["model_lift_over_trivial"] = round(sep["pooled_auc"] - sep["trivial_baseline_pooled_auc"], 4)
    report["separability"] = sep
    print(f"\n[4] SEPARABILITY  per-recording AUC: " +
          ", ".join(f"{r.split('/')[-1]}={v}" for r, v in per_rec_auc.items()))
    print(f"       per-recording AUC median={sep['per_recording_auc_median']} range={sep['per_recording_auc_range']}"
          f"  (DEPLOYMENT-relevant)")
    print(f"       pooled AUC={sep['pooled_auc']} (dragged down by cross-recording scale spread)")
    print(f"       trivial no-model baseline AUC={sep['trivial_baseline_pooled_auc']}  "
          f"-> model lift = {sep['model_lift_over_trivial']}")

    # ---- 5. LOCALIZATION: per-channel error increase, NORMALIZED by nominal per-channel MSE ----
    base_ch = np.mean([((onnx_recon(evalh[r]) - evalh[r])**2).mean(axis=2).mean(axis=0) for r in evalh], axis=0)
    loc = {}
    for fk in FAULTS:
        incs = []
        for r in evalh:
            f = faulted[r][fk]
            inc = ((onnx_recon(f)-f)**2).mean(axis=2).mean(axis=0) - ((onnx_recon(evalh[r])-evalh[r])**2).mean(axis=2).mean(axis=0)
            incs.append(inc)
        inc = np.mean(incs, axis=0)
        norm_inc = inc / np.where(base_ch < 1e-9, 1e-9, base_ch)   # relative to each channel's nominal error
        loc[fk] = {"raw_top3": [chans[i] for i in np.argsort(inc)[-3:][::-1]],
                   "normalized_top3": [chans[i] for i in np.argsort(norm_inc)[-3:][::-1]]}
    report["localization"] = {"note": "SANITY CHECK ONLY — an AE's largest residual is trivially on the "
                              "perturbed channel; this is not diagnosis. Thruster faults hit a RANDOM "
                              "thruster per window, so thruster localization is bank-level, not unit-level. "
                              "raw_top3 is dominated by the worst-reconstructed channel (temp_int); "
                              "normalized_top3 divides by each channel's nominal error.",
                              "nominal_per_channel_mse": {chans[i]: round(float(base_ch[i]), 4) for i in range(C)},
                              "by_fault": loc}
    print(f"\n[5] LOCALIZATION (sanity check, normalized by nominal per-channel error):")
    for fk in FAULTS:
        print(f"       {fk:18s} -> {loc[fk]['normalized_top3']}")

    # ---- 6. OPERATING curve: nominal pooled ONCE; faults pooled across faults ----
    nom_scores = np.concatenate([err_of(evalh[r]) for r in evalh])
    fault_scores = np.concatenate([err_of(faulted[r][fk]) for r in evalh for fk in FAULTS])
    ys = np.r_[np.zeros(len(nom_scores)), np.ones(len(fault_scores))]
    ss = np.r_[nom_scores, fault_scores]
    op = []
    for q in (0.90, 0.95, 0.98, 0.99):
        t = float(np.quantile(nom_scores, q))
        op.append({"nominal_quantile": q, "threshold": round(t, 4),
                   "far": round(float((nom_scores > t).mean()), 3),
                   "recall": round(float((fault_scores > t).mean()), 3)})
    report["operating"] = {"global_threshold_auc": round(float(roc_auc_score(ys, ss)), 4),
                           "n_nominal_eval": int(len(nom_scores)), "n_fault_eval": int(len(fault_scores)),
                           "points": op}
    print(f"\n[6] OPERATING (global threshold, n_nominal={len(nom_scores)} n_fault={len(fault_scores)}):")
    for o in op:
        print(f"       thr@nom-q{o['nominal_quantile']:.2f}={o['threshold']:.3f}  "
              f"FAR={o['far']:.3f}  recall={o['recall']:.3f}")

    out = HERE / ("test_report_int8.json" if a.int8 else "test_report.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\n  wrote models/uuv/{out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
