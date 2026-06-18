#!/usr/bin/env python3
"""THESEUS ingest adapter — NASA N-CMAPSS (Turbofan Degradation Sim Data Set 2, RUL).

Reads data/datasets/ncmapss/N-CMAPSS_DS02-006.h5 (US-Gov public domain; Arias Chao
et al. 2021) and emits the loop data contract: the operating-condition channels (W)
+ measured sensor channels (X_s) as numeric features, with LAST column = `rul`
(remaining useful life, from the dataset's own Y array).

N-CMAPSS is the realistic, full-flight-condition successor to C-MAPSS: degradation is
propagated under real recorded flight envelopes, so this exercises the RUL/degradation
beat under varying operating points (closer to a warship GT than C-MAPSS steady state).

The HDF5 stores per-split arrays (`W_dev`/`X_s_dev`/`Y_dev`/`A_dev` and `_test`) plus
variable-name arrays (`W_var`/`X_s_var`/...). This adapter reads the var-name arrays
from the file (so column names track the real file), maps W+X_s -> features, Y -> rul.
At 1 Hz the dev split is millions of rows, so `--stride` subsamples (default 100) and
`--rows` caps; this is honest downsampling, documented in DOWNLOADS.md.

NOTE: like cmapss.py, this satisfies the uniform contract (last col = target); it becomes
loop-live once demo/retrain.py's TARGET is parametrized to `rul` (flagged to WARHACKER).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

try:
    import h5py
except ImportError:  # pragma: no cover - dependency surfaced at runtime
    h5py = None

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out" / "ncmapss.csv"
DEFAULT_SRC = ROOT / "data" / "datasets" / "ncmapss" / "N-CMAPSS_DS02-006.h5"

# Canonical fallbacks (Arias Chao et al. 2021) if the file omits the *_var name arrays.
_W_FALLBACK = ["alt", "Mach", "TRA", "T2"]
_XS_FALLBACK = ["T24", "T30", "T48", "T50", "P15", "P2", "P21", "P24",
                "Ps30", "P40", "P50", "Nf", "Nc", "Wf"]


def _names(f, key: str, n_cols: int, fallback: list[str]) -> list[str]:
    """Decode a *_var name array into a list[str]; fall back to canonical names."""
    arr = f.get(key)
    if arr is not None:
        out = []
        for v in np.array(arr).flatten():
            out.append(v.decode("utf-8").strip() if isinstance(v, (bytes, bytearray)) else str(v).strip())
        if len(out) == n_cols:
            return out
    if len(fallback) == n_cols:
        return list(fallback)
    return [f"{key.split('_')[0]}_{i}" for i in range(n_cols)]


def main() -> int:
    ap = argparse.ArgumentParser(description="NASA N-CMAPSS -> loop data contract (RUL).")
    ap.add_argument("--file", default=str(DEFAULT_SRC), help="path to N-CMAPSS_DSxx.h5")
    ap.add_argument("--split", default="dev", choices=["dev", "test"], help="dev=train units, test=test units")
    ap.add_argument("--units", default="", help="comma-separated unit ids to keep (default: all in split)")
    ap.add_argument("--stride", type=int, default=100, help="subsample 1 row per N (1 Hz source; default 100)")
    ap.add_argument("--rows", type=int, default=0, help="cap output rows (0 = no cap)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    if h5py is None:
        print("  h5py not installed: pip install h5py")
        return 1
    src = Path(a.file)
    if not src.exists():
        print(f"  source missing: {src}  (download N-CMAPSS_DS02-006.h5 — see DOWNLOADS.md)")
        return 1

    s = a.split
    stride = max(1, a.stride)
    with h5py.File(src, "r") as f:
        for req in (f"W_{s}", f"X_s_{s}", f"Y_{s}", f"A_{s}"):
            if req not in f:
                print(f"  unexpected HDF5 layout: missing '{req}' in {src.name}")
                return 1
        W = f[f"W_{s}"][::stride]
        X_s = f[f"X_s_{s}"][::stride]
        Y = np.array(f[f"Y_{s}"][::stride]).reshape(-1)
        A = f[f"A_{s}"][::stride]
        w_names = _names(f, "W_var", W.shape[1], _W_FALLBACK)
        xs_names = _names(f, "X_s_var", X_s.shape[1], _XS_FALLBACK)
        a_names = _names(f, "A_var", A.shape[1], ["unit", "cycle", "Fc", "hs"])

    keep = np.ones(len(Y), dtype=bool)
    if a.units.strip():
        try:
            unit_col = a_names.index("unit")
        except ValueError:
            unit_col = 0
        wanted = {float(u) for u in a.units.split(",") if u.strip()}
        keep = np.isin(A[:, unit_col].astype(float), list(wanted))

    feats = list(w_names) + list(xs_names)
    fieldnames = feats + ["rul"]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fieldnames)
        for i in range(len(Y)):
            if not keep[i]:
                continue
            row = [f"{v:.6g}" for v in W[i]] + [f"{v:.6g}" for v in X_s[i]] + [f"{Y[i]:.6g}"]
            w.writerow(row)
            written += 1
            if a.rows and written >= a.rows:
                break

    units_seen = sorted({int(u) for u in np.unique(A[keep][:, a_names.index("unit") if "unit" in a_names else 0])})
    print(f"  N-CMAPSS {src.name} [{s}] -> {out if out.is_absolute() else out.relative_to(ROOT)} · "
          f"rows={written} · features={len(feats)} (W={len(w_names)}+X_s={len(xs_names)}) · "
          f"stride={stride} · units={units_seen} · target=rul (last)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
