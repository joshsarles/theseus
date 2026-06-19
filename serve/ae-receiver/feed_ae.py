#!/usr/bin/env python3
"""Synthetic feeder for theseus-uuv AE receiver.

Generates 23-channel BlueROV2-like records from the scaler.json statistics
(mean, std) and POSTs them one-at-a-time to the receiver's /stream-item
endpoint.  Every ~6th record is an injected anomaly (several channels
spiked several sigma above normal) so you can verify that:
  - normal windows produce low active_anomaly_score
  - anomaly windows produce high active_anomaly_score

Usage:
  python3 feed_ae.py                               # default url, 2s interval, 80 records
  python3 feed_ae.py --url http://127.0.0.1:54547/stream-item --interval 0.2 --n 120
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_URL      = "http://127.0.0.1:54547/stream-item"
DEFAULT_INTERVAL = 2.0
DEFAULT_N        = 80
DEFAULT_SCALER   = str(
    Path(__file__).resolve().parent.parent.parent / "models" / "uuv" / "scaler.json"
)
ANOMALY_EVERY    = 6          # inject one anomaly record every N records
ANOMALY_SIGMA    = 6.0        # spike magnitude in standard deviations
ANOMALY_N_CHAN   = 5          # how many channels to spike per anomaly record
SEED             = 42
TOPIC_ID         = "uuv-telemetry"


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def main() -> None:
    ap = argparse.ArgumentParser(description="Synthetic feeder for uuv-ae receiver")
    ap.add_argument("--url",      default=DEFAULT_URL,      help="POST target URL")
    ap.add_argument("--interval", default=DEFAULT_INTERVAL, type=float,
                    help="seconds between records (default 2.0)")
    ap.add_argument("--n",        default=DEFAULT_N,        type=int,
                    help="total records to send (default 80)")
    ap.add_argument("--scaler",   default=DEFAULT_SCALER,
                    help="path to scaler.json (for mean/std)")
    ap.add_argument("--anomaly-every", type=int, default=ANOMALY_EVERY,
                    help="inject 1 anomaly every N records; 0 = never (calm live own-systems tile)")
    a = ap.parse_args()
    anomaly_every = a.anomaly_every

    # load scaler
    sc       = json.loads(Path(a.scaler).read_text())
    channels = sc["channels"]            # list[str], len=23
    mean     = np.asarray(sc["mean"],  dtype=np.float64)
    std_raw  = np.asarray(sc["std"],   dtype=np.float64)
    std      = np.where(std_raw < 1e-6, 1.0, std_raw)

    rng = np.random.default_rng(SEED)
    n_ch = len(channels)
    walk = np.zeros(n_ch)          # AR(1) state for temporally-smooth "normal" telemetry

    print(f"[feed_ae] sending {a.n} records to {a.url}  interval={a.interval}s")
    print(f"[feed_ae] anomaly injection: every {ANOMALY_EVERY}th record, "
          f"{ANOMALY_N_CHAN} channels spiked at ±{ANOMALY_SIGMA}σ")
    print()

    i = 0
    while a.n <= 0 or i < a.n:          # --n <= 0 → stream forever (live demo)
        i += 1
        is_anomaly = anomaly_every > 0 and (i % anomaly_every == 0)

        if is_anomaly:
            # spike ANOMALY_N_CHAN randomly-chosen channels by ANOMALY_SIGMA σ
            values = rng.standard_normal(n_ch) * std + mean
            spike_idx = rng.choice(n_ch, size=ANOMALY_N_CHAN, replace=False)
            signs = rng.choice([-1, 1], size=ANOMALY_N_CHAN)
            for si, sign in zip(spike_idx, signs):
                values[si] += sign * ANOMALY_SIGMA * std[si]
            label = "ANOMALY"
        else:
            # normal: a SMOOTH AR(1) walk near the mean. Real vehicle telemetry is temporally
            # correlated and the Conv1d sequence AE learned that structure — feeding i.i.d.
            # Gaussian noise reconstructs poorly (high error) even though each sample is in-range.
            walk = 0.92 * walk + 0.08 * rng.standard_normal(n_ch)
            values = mean + walk * std
            label = "normal "

        record = {ch: float(v) for ch, v in zip(channels, values)}
        record["record_id"] = i      # for caller-side anomaly bookkeeping

        payload = {"topic_id": TOPIC_ID, "data": [record]}
        try:
            resp = _post_json(a.url, payload)
            wf   = resp.get("window_full", False)
            ls   = resp.get("last_score")
            score_str = f"  score={ls:.6f}" if ls is not None else ""
            print(f"  rec {i:3d}  [{label}]  window_full={wf}{score_str}")
        except Exception as exc:
            # Resilient: a transient error (e.g. ConnectionResetError while the container is
            # still booting) must NOT kill a continuous feed — log and keep streaming.
            print(f"  rec {i:3d}  [{label}]  POST failed ({type(exc).__name__}): {exc}")

        time.sleep(a.interval)

    print("\n[feed_ae] done — check /history for scored windows")


if __name__ == "__main__":
    main()
