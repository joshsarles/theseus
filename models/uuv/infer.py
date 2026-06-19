#!/usr/bin/env python3
"""THESEUS — torch-free edge inference for `theseus-uuv` (Raspberry Pi 5, 4 GB or 8 GB).

This is the DEPLOYABLE serving path. Dependencies are **numpy + onnxruntime ONLY** — no torch,
sklearn, or pandas — so it installs and runs on a 64-bit Raspberry Pi with `pip install
numpy onnxruntime` (both ship aarch64 manylinux wheels). It loads the ONNX model + the saved
scaler, slides 6.4 s windows over telemetry, scores reconstruction error, and flags windows above
the threshold. Advisory only — a human decides.

Memory/latency: int8 model ~154 KB, ~52 MB RSS, sub-millisecond per window on one core — fits a
4 GB Pi with vast margin (the 8 GB Pi only adds headroom; RAM is never the constraint here).

  # score a telemetry CSV (the ingest/ardusub.py output), int8 model, single-thread:
  python3 models/uuv/infer.py --csv ingest/out/ardusub.csv --int8

  # calibrate the alarm threshold in-situ on the first half of (assumed-nominal) telemetry:
  python3 models/uuv/infer.py --csv ingest/out/ardusub.csv --int8 --calibrate

  # restrict to one recording / set an explicit threshold:
  python3 models/uuv/infer.py --csv ingest/out/ardusub.csv --recording limited/7m --threshold 0.42
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCALER = HERE / "scaler.json"


def _peak_rss_mb() -> float:
    """Inference-process peak RSS in MB. ru_maxrss is BYTES on macOS, KILOBYTES on Linux (the Pi)."""
    import resource
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


class UUVScorer:
    """Loads the theseus-uuv ONNX + scaler; scores standardized (C, W) windows by reconstruction error."""

    def __init__(self, int8: bool = True, threads: int = 1, scaler_path: Path = SCALER):
        sc = json.loads(Path(scaler_path).read_text())
        self.channels = sc["channels"]
        self.mean = np.asarray(sc["mean"], dtype=np.float32)
        self.std = np.where(np.asarray(sc["std"], dtype=np.float32) < 1e-6, 1.0,
                            np.asarray(sc["std"], dtype=np.float32))
        self.W = int(sc["window"])
        self.threshold = float(sc["threshold"])      # shipped default; override or --calibrate
        self.target_far = float(sc.get("target_far", 0.02))

        name = "uuv_seq_ae_int8.onnx" if int8 else "uuv_seq_ae.onnx"
        self.model_path = ROOT / "models" / "onnx" / name
        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX model missing: {self.model_path} (run train_uuv_ae.py)")
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads        # 1 = mimic a single Pi core; raise on the 8 GB Pi if desired
        so.inter_op_num_threads = threads
        self.sess = ort.InferenceSession(self.model_path.as_posix(), so,
                                         providers=["CPUExecutionProvider"])
        self.in_name = self.sess.get_inputs()[0].name

    def standardize(self, window: np.ndarray) -> np.ndarray:
        """window: raw (C, W) -> standardized (C, W) using the saved training stats."""
        return ((window - self.mean[:, None]) / self.std[:, None]).astype(np.float32)

    def score(self, std_window: np.ndarray) -> float:
        """Reconstruction-error anomaly score for ONE standardized (C, W) window."""
        x = std_window[None, :, :].astype(np.float32)           # (1, C, W)
        recon = self.sess.run(None, {self.in_name: x})[0]
        return float(((recon - x) ** 2).mean())

    def flag(self, std_window: np.ndarray) -> tuple[float, bool]:
        s = self.score(std_window)
        return s, s > self.threshold


def stream_windows(csv_path: Path, channels: list[str], W: int, stride: int,
                   only_recording: str | None):
    """Yield (recording, t_start, raw_window[C,W]) sliding within each recording. stdlib csv only."""
    rows = defaultdict(list)
    times = defaultdict(list)
    with Path(csv_path).open() as f:
        rdr = csv.reader(f)
        header = next(rdr)
        idx = {c: header.index(c) for c in channels}
        ti = header.index("t") if "t" in header else 1
        ri = header.index("recording") if "recording" in header else 0
        for r in rdr:
            rec = r[ri]
            if only_recording and rec != only_recording:
                continue
            rows[rec].append([float(r[idx[c]]) for c in channels])
            times[rec].append(float(r[ti]))
    for rec, data in rows.items():
        arr = np.asarray(data, dtype=np.float32)                # (T, C)
        for i in range(0, len(arr) - W + 1, stride):
            yield rec, times[rec][i], arr[i:i + W].T            # (C, W)


def main() -> int:
    ap = argparse.ArgumentParser(description="Torch-free edge inference for theseus-uuv.")
    ap.add_argument("--csv", default=str(ROOT / "ingest" / "out" / "ardusub.csv"),
                    help="telemetry CSV in the ingest/ardusub.py format (recording, t, <channels>)")
    ap.add_argument("--int8", action="store_true", help="use the int8 ONNX (recommended on ARM)")
    ap.add_argument("--threads", type=int, default=1, help="onnxruntime threads (1 = one Pi core)")
    ap.add_argument("--recording", default=None, help="restrict to one recording id")
    ap.add_argument("--stride", type=int, default=None, help="window stride (default W/4)")
    ap.add_argument("--threshold", type=float, default=None, help="override the alarm threshold")
    ap.add_argument("--calibrate", action="store_true",
                    help="set threshold in-situ from the first half of the stream (assumed nominal)")
    a = ap.parse_args()

    if not Path(a.csv).exists():
        print(f"  telemetry CSV missing: {a.csv} (run `python3 ingest/ardusub.py`)"); return 1

    scorer = UUVScorer(int8=a.int8, threads=a.threads)
    stride = a.stride or max(1, scorer.W // 4)
    if a.threshold is not None:
        scorer.threshold = a.threshold

    wins = list(stream_windows(Path(a.csv), scorer.channels, scorer.W, stride, a.recording))
    if not wins:
        print("  no windows produced (check --recording / CSV / channel names)"); return 1

    # optional in-situ calibration: threshold = target-FAR quantile of recon error on first-half windows
    if a.calibrate:
        half = max(1, len(wins) // 2)
        cal = [scorer.score(scorer.standardize(w)) for _, _, w in wins[:half]]
        scorer.threshold = float(np.quantile(cal, 1 - scorer.target_far))
        print(f"  in-situ calibrated threshold (q{1-scorer.target_far:.2f} of {half} nominal windows): "
              f"{scorer.threshold:.4f}")

    print(f"THESEUS · theseus-uuv edge inference  "
          f"({'int8' if a.int8 else 'fp32'}, {scorer.model_path.stat().st_size/1024:.1f} KB, "
          f"{a.threads} thread, thr={scorer.threshold:.4f})")

    t0 = time.time()
    n_flag = 0
    for rec, t, w in wins:
        s, flagged = scorer.flag(scorer.standardize(w))
        if flagged:
            n_flag += 1
            print(f"  ⚠ ADVISORY  {rec:20s} t={t:7.1f}s  score={s:.4f} > {scorer.threshold:.4f}  "
                  f"→ recommend watchstander review")
    dt = time.time() - t0

    print(f"\n  scored {len(wins)} windows · {n_flag} flagged ({100*n_flag/len(wins):.1f}%) · "
          f"{dt/len(wins)*1000:.3f} ms/window · peak RSS {_peak_rss_mb():.1f} MB")
    print(f"  (advisory only — the watchstander decides; nothing is actioned automatically)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
