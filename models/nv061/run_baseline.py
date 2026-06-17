#!/usr/bin/env python3
# coding=utf-8
"""
NV061 trajectory-prediction baseline runner for project THESEUS.

Reproduces the TrAISformer (arXiv:2109.03958) vessel-trajectory-prediction
pipeline on the `ct_dma` dataset, on OUR hardware (Apple MPS), without editing
the upstream clone. The upstream repo hardcodes `device=cuda:0` and
`max_epochs=50`; this runner inserts the clone on sys.path and overrides the
Config (device / epochs / data dir / batch size / n_samples) at runtime.

It also computes a constant-velocity (CV) "floor" baseline on the *same* eval
harness, which is the NV061 reference the learned model must beat.

HONESTY LABELS
  [published]     = number copied from the paper (Table I), nautical miles.
  [verified]      = number this script actually produced on our box (short run).
  [pipeline-only] = produced by a deliberately short/reduced run; NOT the
                    published full-50-epoch scoreboard.

The upstream eval reports error in km (haversine, R=6371). The paper reports
nautical miles. We report BOTH (1 nmi = 1.852 km) and replicate the upstream
eval constants verbatim so our numbers are directly comparable to Table I.

Usage (short pipeline-verification run, the default):
    python3 run_baseline.py

    python3 run_baseline.py --smoke           # dataset stats + 1 fwd + 1 eval batch
    python3 run_baseline.py --epochs 3 --max-train 3000 --max-test 512 --n-samples 8
"""
import argparse
import json
import os
import sys
import time
import logging

import numpy as np
import torch

# --- Paths -------------------------------------------------------------------
REPO_DIR = "/Users/force/Developer/Theseus/data/datasets/traisformer"
DATA_DIR = os.path.join(REPO_DIR, "data", "ct_dma")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT_DIR, exist_ok=True)

NMI_PER_KM = 1.0 / 1.852  # 1 nautical mile = 1.852 km

# --- Logging -----------------------------------------------------------------
LOG_PATH = os.path.join(OUT_DIR, "run.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, mode="w"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("nv061")


def pick_device(requested: str) -> torch.device:
    if requested == "cpu":
        return torch.device("cpu")
    if requested == "mps":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        log.warning("MPS requested but not available; falling back to CPU.")
        return torch.device("cpu")
    if requested == "cuda" and torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def import_repo():
    """Insert the upstream clone on sys.path and import its modules.

    Import order matters: `trainers` must be imported first so the circular
    `trainers <-> trAISformer` import resolves (trAISformer binds the partially
    loaded trainers module by name only). Importing trAISformer first raises
    ImportError on `from trAISformer import TB_LOG`.
    """
    if REPO_DIR not in sys.path:
        sys.path.insert(0, REPO_DIR)
    import trainers  # noqa: E402  (triggers safe circular resolution)
    import models  # noqa: E402
    import datasets  # noqa: E402
    import utils  # noqa: E402
    from config_trAISformer import Config  # noqa: E402
    return trainers, models, datasets, utils, Config


def load_phase(datasets_mod, Config, cf, phase, filename, max_traj=None):
    """Replicate trAISformer.py data loading + filtering, then optionally cap."""
    import pickle
    datapath = os.path.join(cf.datadir, filename)
    with open(datapath, "rb") as f:
        l_raw = pickle.load(f)
    moving_threshold = 0.05
    for V in l_raw:
        try:
            moving_idx = np.where(V["traj"][:, 2] > moving_threshold)[0][0]
        except Exception:
            moving_idx = len(V["traj"]) - 1
        V["traj"] = V["traj"][moving_idx:, :]
    data = [x for x in l_raw if not np.isnan(x["traj"]).any() and len(x["traj"]) > cf.min_seqlen]
    n_total = len(data)
    if max_traj is not None and max_traj < n_total:
        data = data[:max_traj]
    ds = datasets_mod.AISDataset(data, max_seqlen=cf.max_seqlen + 1, device=torch.device("cpu"))
    log.info(f"  [{phase}] raw={len(l_raw)} kept={n_total} used={len(data)}")
    return data, ds


def haversine(input_coords, pred_coords):
    """km haversine, replicated from upstream utils.haversine (R=6371)."""
    R = 6371.0
    lat_err = pred_coords[..., 0] - input_coords[..., 0]
    lon_err = pred_coords[..., 1] - input_coords[..., 1]
    a = torch.sin(lat_err / 2) ** 2 + torch.cos(input_coords[:, :, 0]) * torch.cos(
        pred_coords[:, :, 0]
    ) * torch.sin(lon_err / 2) ** 2
    c = 2 * torch.atan2(torch.sqrt(a), torch.sqrt(1 - a))
    return R * c


def eval_trAISformer(trainers_mod, model, dl, cf, device, init_seqlen, n_eval_steps, n_samples,
                     max_batches=None):
    """Replicate the upstream trAISformer.py evaluation block verbatim.

    Returns pred_errors (km) of shape (n_eval_steps,) = ensemble-min over samples,
    mask-weighted-averaged over the test set.
    """
    pi = torch.acos(torch.zeros(1)).item() * 2
    v_ranges = torch.tensor([2.0, 3.0, 0.0, 0.0]).to(device)
    v_roi_min = torch.tensor([float(model.lat_min), -7.0, 0.0, 0.0]).to(device)
    max_seqlen = init_seqlen + n_eval_steps

    model.eval()
    l_min_errors, l_masks = [], []
    with torch.no_grad():
        for it, (seqs, masks, seqlens, mmsis, time_starts) in enumerate(dl):
            if max_batches is not None and it >= max_batches:
                break
            seqs_init = seqs[:, :init_seqlen, :].to(device)
            masks = masks[:, :max_seqlen].to(device)
            bs = seqs.shape[0]
            error_ens = torch.zeros((bs, max_seqlen - init_seqlen, n_samples)).to(device)
            for i_sample in range(n_samples):
                preds = trainers_mod.sample(
                    model, seqs_init, max_seqlen - init_seqlen,
                    temperature=1.0, sample=True,
                    sample_mode=cf.sample_mode, r_vicinity=cf.r_vicinity, top_k=cf.top_k,
                )
                inputs = seqs[:, :max_seqlen, :].to(device)
                input_coords = (inputs * v_ranges + v_roi_min) * pi / 180
                pred_coords = (preds * v_ranges + v_roi_min) * pi / 180
                d = haversine(input_coords, pred_coords) * masks
                error_ens[:, :, i_sample] = d[:, init_seqlen:]
            l_min_errors.append(error_ens.min(dim=-1).values)
            l_masks.append(masks[:, init_seqlen:])

    m_masks = torch.cat(l_masks, dim=0)
    min_errors = torch.cat(l_min_errors, dim=0) * m_masks
    pred_errors = min_errors.sum(dim=0) / m_masks.sum(dim=0)
    return pred_errors.detach().cpu().numpy()


def eval_constant_velocity(model, dl, cf, device, init_seqlen, n_eval_steps, max_batches=None):
    """Constant-velocity 'floor' baseline on the SAME haversine harness.

    Propagates the mean per-step (dlat,dlon) over the init window linearly for
    n_eval_steps. No learning, no sampling. This is the NV061 reference floor.
    """
    pi = torch.acos(torch.zeros(1)).item() * 2
    v_ranges = torch.tensor([2.0, 3.0, 0.0, 0.0]).to(device)
    v_roi_min = torch.tensor([float(model.lat_min), -7.0, 0.0, 0.0]).to(device)
    max_seqlen = init_seqlen + n_eval_steps

    l_err, l_masks = [], []
    with torch.no_grad():
        for it, (seqs, masks, seqlens, mmsis, time_starts) in enumerate(dl):
            if max_batches is not None and it >= max_batches:
                break
            seqs = seqs.to(device)
            masks = masks[:, :max_seqlen].to(device)
            bs = seqs.shape[0]
            init = seqs[:, :init_seqlen, :]  # (bs, init, 4)
            # mean per-step velocity in normalized lat/lon over the init window
            vel = (init[:, -1, :2] - init[:, 0, :2]) / max(init_seqlen - 1, 1)  # (bs,2)
            last = init[:, -1, :2]  # (bs,2)
            steps = torch.arange(1, n_eval_steps + 1, device=device).float().view(1, -1, 1)
            pred_pos = last.unsqueeze(1) + steps * vel.unsqueeze(1)  # (bs, n_eval, 2)
            full = seqs[:, :max_seqlen, :]
            preds = full.clone()
            preds[:, init_seqlen:, :2] = pred_pos
            input_coords = (full * v_ranges + v_roi_min) * pi / 180
            pred_coords = (preds * v_ranges + v_roi_min) * pi / 180
            d = haversine(input_coords, pred_coords) * masks
            l_err.append(d[:, init_seqlen:])
            l_masks.append(masks[:, init_seqlen:])

    m_masks = torch.cat(l_masks, dim=0)
    errs = torch.cat(l_err, dim=0) * m_masks
    pred_errors = errs.sum(dim=0) / m_masks.sum(dim=0)
    return pred_errors.detach().cpu().numpy()


def horizon_table(pred_errors_km):
    """Extract 1h/2h/3h errors. Data is 10-min sampled -> 6 steps/hour."""
    out = {}
    for hrs, idx in [(1, 6), (2, 12), (3, 18)]:
        if idx < len(pred_errors_km):
            km = float(pred_errors_km[idx])
            out[f"{hrs}h"] = {"km": round(km, 4), "nmi": round(km * NMI_PER_KM, 4)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps", choices=["mps", "cpu", "cuda"])
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-train", type=int, default=1500, help="cap #train trajectories")
    ap.add_argument("--max-test", type=int, default=256, help="cap #test trajectories for eval")
    ap.add_argument("--max-train-batches", type=int, default=None, help="cap batches/epoch")
    ap.add_argument("--n-samples", type=int, default=4, help="ensemble samples at eval (paper=16)")
    ap.add_argument("--smoke", action="store_true", help="stats + 1 fwd + 1 eval batch, no training")
    args = ap.parse_args()

    t0 = time.time()
    trainers_mod, models_mod, datasets_mod, utils_mod, Config = import_repo()
    utils_mod.set_seed(42)

    device = pick_device(args.device)
    log.info(f"=== NV061 TrAISformer baseline | device={device} | torch={torch.__version__} ===")

    # Build + override config (no edit to the upstream clone).
    cf = Config()
    cf.device = device
    cf.datadir = DATA_DIR + os.sep
    cf.max_epochs = args.epochs
    cf.batch_size = args.batch_size
    cf.n_samples = args.n_samples
    init_seqlen = cf.init_seqlen
    n_eval_steps = 6 * 4  # 24 steps = 4 hours @ 10-min sampling (upstream eval window)

    log.info("Loading ct_dma ...")
    train_data, train_ds = load_phase(datasets_mod, Config, cf, "train", cf.trainset_name, args.max_train)
    test_data, test_ds = load_phase(datasets_mod, Config, cf, "test", cf.testset_name, args.max_test)
    cf.final_tokens = 2 * len(train_ds) * cf.max_seqlen

    from torch.utils.data import DataLoader
    train_dl = DataLoader(train_ds, batch_size=cf.batch_size, shuffle=True)
    test_dl = DataLoader(test_ds, batch_size=cf.batch_size, shuffle=False)

    model = models_mod.TrAISformer(cf, partition_model=None)
    n_params = sum(p.numel() for p in model.parameters())
    log.info(f"Model params: {n_params:,}")

    # Device probe: confirm a fwd+bwd works on the chosen device; else fall back.
    try:
        model = model.to(device)
        probe_seqs, probe_masks, *_ = next(iter(train_dl))
        probe_seqs = probe_seqs.to(device)
        logits, loss = model(probe_seqs, masks=probe_masks[:, :-1].to(device), with_targets=True)
        probe_loss = float(loss.mean().detach())
        loss.mean().backward()
        model.zero_grad()
        log.info(f"[verified] device probe OK on {device}; probe loss={probe_loss:.4f}")
    except Exception as e:
        log.warning(f"Device probe failed on {device} ({e}); falling back to CPU.")
        device = torch.device("cpu")
        cf.device = device
        model = models_mod.TrAISformer(cf, partition_model=None).to(device)

    result = {
        "device": str(device),
        "torch": torch.__version__,
        "n_params": int(n_params),
        "config": {
            "epochs": cf.max_epochs, "batch_size": cf.batch_size, "n_samples": cf.n_samples,
            "init_seqlen": init_seqlen, "n_eval_steps": n_eval_steps,
            "max_train": args.max_train, "max_test": args.max_test,
            "mode": cf.mode, "sample_mode": cf.sample_mode,
        },
        "dataset": {"train_used": len(train_ds), "test_used": len(test_ds)},
        "run_type": "smoke" if args.smoke else "short-pipeline-verification",
    }

    if args.smoke:
        log.info("[smoke] forward pass + single eval batch (no training)")
        cv = eval_constant_velocity(model, test_dl, cf, device, init_seqlen, n_eval_steps, max_batches=1)
        tf = eval_trAISformer(trainers_mod, model, test_dl, cf, device, init_seqlen, n_eval_steps,
                              n_samples=min(2, cf.n_samples), max_batches=1)
        result["smoke_untrained_trAISformer_km_curve"] = [round(float(x), 4) for x in tf]
        result["smoke_constant_velocity"] = horizon_table(cv)
        result["elapsed_sec"] = round(time.time() - t0, 1)
        _save(result, tf, cv)
        log.info("[smoke] done.")
        return

    # --- Short real training loop (custom; avoids upstream's py2 `.next()` + ---
    # --- deprecated matplotlib plotting in Trainer.train()). --------------------
    optimizer = model.configure_optimizers(cf)
    from tqdm import tqdm
    for epoch in range(cf.max_epochs):
        model.train()
        losses = []
        pbar = tqdm(enumerate(train_dl), total=len(train_dl), desc=f"epoch {epoch+1}")
        for it, (seqs, masks, seqlens, mmsis, time_starts) in pbar:
            if args.max_train_batches is not None and it >= args.max_train_batches:
                break
            seqs = seqs.to(device)
            masks_in = masks[:, :-1].to(device)
            logits, loss = model(seqs, masks=masks_in, with_targets=True)
            loss = loss.mean()
            model.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cf.grad_norm_clip)
            optimizer.step()
            losses.append(float(loss.item()))
            pbar.set_description(f"epoch {epoch+1} loss {loss.item():.4f}")
        log.info(f"[verified] epoch {epoch+1} mean train loss = {np.mean(losses):.5f}")

    # --- Evaluation (upstream harness; km -> nmi) -----------------------------
    log.info(f"Evaluating: TrAISformer ensemble (n_samples={cf.n_samples}) + CV floor ...")
    tf_km = eval_trAISformer(trainers_mod, model, test_dl, cf, device, init_seqlen, n_eval_steps,
                             n_samples=cf.n_samples)
    cv_km = eval_constant_velocity(model, test_dl, cf, device, init_seqlen, n_eval_steps)

    result["trAISformer_short_run"] = horizon_table(tf_km)      # [verified][pipeline-only]
    result["constant_velocity_floor"] = horizon_table(cv_km)    # [verified] reference floor
    result["published_scoreboard_nmi"] = {                      # [published] Table I, arXiv:2109.03958
        "TrAISformer": {"1h": 0.48, "2h": 0.94, "3h": 1.64},
        "GeoTrackNet": {"1h": 0.72, "2h": 1.59, "3h": 2.67},
        "Clustering_LSTM_seq2seq_att": {"1h": 0.78, "2h": 1.93, "3h": 3.66},
        "LSTM_seq2seq_att": {"1h": 3.35, "2h": 6.41, "3h": 9.65},
        "Conv_seq2seq": {"1h": 4.23, "2h": 6.77, "3h": 9.66},
        "LSTM_seq2seq": {"1h": 5.83, "2h": 8.39, "3h": 11.64},
    }
    result["elapsed_sec"] = round(time.time() - t0, 1)
    _save(result, tf_km, cv_km)

    log.info("=== RESULT (1h / 2h / 3h) ===")
    log.info(f"[published] TrAISformer (50 epochs):     0.48 / 0.94 / 1.64 nmi")
    log.info(f"[verified][pipeline-only] TrAISformer:   "
             + " / ".join(f"{result['trAISformer_short_run'][h]['nmi']:.2f}" for h in ['1h','2h','3h']) + " nmi")
    log.info(f"[verified] constant-velocity floor:      "
             + " / ".join(f"{result['constant_velocity_floor'][h]['nmi']:.2f}" for h in ['1h','2h','3h']) + " nmi")
    log.info(f"elapsed = {result['elapsed_sec']}s")


def _save(result, tf_curve_km, cv_curve_km):
    with open(os.path.join(OUT_DIR, "metrics.json"), "w") as f:
        json.dump(result, f, indent=2)
    # full per-step error curves (km + nmi)
    # pred_idx = 0-based forecast-step index. hours_upstream = pred_idx/6, the
    # exact convention used by trAISformer.py (pred_errors[6/12/18] = 1/2/3h).
    import csv
    with open(os.path.join(OUT_DIR, "error_curve.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pred_idx", "hours_upstream", "trAISformer_km", "trAISformer_nmi", "cv_km", "cv_nmi"])
        n = max(len(tf_curve_km), len(cv_curve_km))
        for i in range(n):
            tfk = float(tf_curve_km[i]) if i < len(tf_curve_km) else ""
            cvk = float(cv_curve_km[i]) if i < len(cv_curve_km) else ""
            w.writerow([
                i, round(i / 6, 3),
                round(tfk, 4) if tfk != "" else "",
                round(tfk * NMI_PER_KM, 4) if tfk != "" else "",
                round(cvk, 4) if cvk != "" else "",
                round(cvk * NMI_PER_KM, 4) if cvk != "" else "",
            ])
    log.info(f"Saved metrics.json + error_curve.csv + run.log to {OUT_DIR}")


if __name__ == "__main__":
    main()
