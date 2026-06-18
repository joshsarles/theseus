"""THESEUS Fleet-Learning Miniature — Ship Node.

Each ship is a self-contained subsystem that operates under DDIL (Denied,
Degraded, Intermittent, Limited communications). Each:
  1. Trains a LOCAL model on its OWN sensor slice — no cross-ship data access.
  2. Signs its delta as an in-toto DSSE attestation (Ed25519, via fleet/signing.py).
  3. Writes the signed delta + chain leaf to its output dir for pickup by the fleet brain.

SCENARIO — Ship Contact Range Estimation
=========================================
A fleet of two ships tracks surface contacts using EO/IR sensors. The ships
operate at different ranges from their assigned patrol sectors:
  - MACHINERY (Ship 1 / pi1): observes contacts at 0–10 km (NEAR sector)
  - CONTACTS   (Ship 2 / pi2): observes contacts at 10–25 km (FAR sector)

Each ship trains a Ridge regressor to estimate DETECTION QUALITY from five
sensor-derived features. The true underlying relationship is LINEAR and identical
for both ships — but neither ship can estimate the global model from its local
data alone (the NEAR model extrapolates badly beyond 10 km; the FAR model
extrapolates badly below 10 km). The fleet brain's FedAvg merge recovers the
global model with near-oracle performance.

This demonstrates the core federated learning value proposition:
  - Local models good in their regime; poor outside it
  - Fleet model is good everywhere, trained on no raw data sharing

Features (5):
  0: range_n          — contact range, normalized 0..1 over full fleet range (0..25 km)
  1: bearing_sin      — sin(bearing)
  2: bearing_cos      — cos(bearing)
  3: signal_n         — received signal strength, normalized 0..1 over -80..-40 dBm
  4: doppler_n        — Doppler shift, normalized -1..1 over -5..+5 Hz

Target: detection quality score (0..1), real linear function + Gaussian noise σ=0.03

Data provenance: generated deterministically from numpy.RandomState seeds.
No real-world privacy concerns. Reproducible. Ship data slices are DISJOINT.

Usage:
  python -m fleet.ship_node --ship-id MACHINERY --node-host local
  python -m fleet.ship_node --ship-id CONTACTS  --node-host local
  # Pi path (when reachable):
  python -m fleet.ship_node --ship-id MACHINERY --node-host pi1.local
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FLEET_DIR = ROOT / "fleet"
KEYS_DIR = FLEET_DIR / "keys"

SHIP_IDS = ["MACHINERY", "CONTACTS"]

# Ship sensor regimes — disjoint, covering the full fleet patrol range
SHIP_CONFIGS = {
    "MACHINERY": {"range_low_km": 0.0,  "range_high_km": 10.0, "seed": 1,  "n_samples": 300},
    "CONTACTS":  {"range_low_km": 10.0, "range_high_km": 25.0, "seed": 2,  "n_samples": 300},
}

# Global range normalization constants (fleet-wide, shared knowledge — NOT data)
RANGE_MAX_KM    = 25.0
SIGNAL_MIN_DBM  = -80.0
SIGNAL_RANGE_DB =  40.0   # -80 to -40 dBm
DOPPLER_MAX_HZ  =   5.0

FEATURE_NAMES = ["range_n", "bearing_sin", "bearing_cos", "signal_n", "doppler_n"]

GREEN, RED, DIM, BOLD, END = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"


def ship_out_dir(ship_id: str) -> Path:
    return FLEET_DIR / "out" / ship_id


# ---------------------------------------------------------------------------
# Synthetic dataset generation (deterministic, seed-fixed)
# ---------------------------------------------------------------------------

def generate_ship_data(
    range_low_km: float,
    range_high_km: float,
    n: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate sensor observations for a ship in its patrol range stratum.

    TRUE MODEL (same for both ships — this is what we're trying to learn):
        quality = 0.5 - 0.3 * range_n + 0.4 * signal_n + 0.1 * doppler_n
                  + N(0, 0.03)
    clamped to [0, 1].
    """
    rng = np.random.RandomState(seed)
    range_km   = rng.uniform(range_low_km, range_high_km, n)
    bearing    = rng.uniform(0.0, 2.0 * np.pi, n)
    signal_dbm = rng.uniform(SIGNAL_MIN_DBM, SIGNAL_MIN_DBM + SIGNAL_RANGE_DB, n)
    doppler_hz = rng.uniform(-DOPPLER_MAX_HZ, DOPPLER_MAX_HZ, n)
    noise      = rng.normal(0.0, 0.03, n)

    # Normalize to fleet-wide constants (train–serving alignment guaranteed)
    range_n   = range_km / RANGE_MAX_KM
    signal_n  = (signal_dbm - SIGNAL_MIN_DBM) / SIGNAL_RANGE_DB
    doppler_n = doppler_hz / DOPPLER_MAX_HZ

    X = np.column_stack([
        range_n, np.sin(bearing), np.cos(bearing), signal_n, doppler_n,
    ]).astype(np.float32)

    y = (0.5 - 0.3 * range_n + 0.4 * signal_n + 0.1 * doppler_n + noise).clip(0.0, 1.0)
    return X, y.astype(np.float32)


def generate_fleet_held_out(n: int = 150, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Fleet brain's held-out eval set: covers the FULL range (0–25 km).

    Ships never see this data. The fleet brain uses it for the eval gate.
    """
    return generate_ship_data(
        range_low_km=0.0, range_high_km=RANGE_MAX_KM, n=n, seed=seed,
    )


def generate_base_model_data(n: int = 50, seed: int = 99) -> tuple[np.ndarray, np.ndarray]:
    """Small global bootstrap dataset for the initial base model (pre-deployment).

    In a real system this is the pre-training corpus. Small intentionally so the
    fleet learning genuinely improves it.
    """
    return generate_ship_data(
        range_low_km=0.0, range_high_km=RANGE_MAX_KM, n=n, seed=seed,
    )


# ---------------------------------------------------------------------------
# Model: closed-form Ridge regression (stdlib + numpy only)
# ---------------------------------------------------------------------------

class RidgeRegressor:
    """Closed-form Ridge regression. w = (X^T X + alpha I)^{-1} X^T y."""

    def __init__(self, alpha: float = 1e-3):
        self.alpha = alpha
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self.n_features_: int = 0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RidgeRegressor":
        X64 = X.astype(np.float64)
        y64 = y.astype(np.float64)
        n, p = X64.shape
        X_aug = np.column_stack([X64, np.ones(n)])
        reg = self.alpha * np.eye(p + 1)
        reg[-1, -1] = 0.0  # don't regularize intercept
        w = np.linalg.solve(X_aug.T @ X_aug + reg, X_aug.T @ y64)
        self.coef_ = w[:p]
        self.intercept_ = float(w[p])
        self.n_features_ = p
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (X.astype(np.float64) @ self.coef_ + self.intercept_).astype(np.float32)

    def to_params(self) -> dict:
        return {
            "coef": self.coef_.tolist(),
            "intercept": self.intercept_,
            "alpha": self.alpha,
            "n_features": self.n_features_,
        }

    @classmethod
    def from_params(cls, params: dict) -> "RidgeRegressor":
        m = cls(alpha=params["alpha"])
        m.coef_ = np.array(params["coef"], dtype=np.float64)
        m.intercept_ = float(params["intercept"])
        m.n_features_ = int(params["n_features"])
        return m


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true.astype(np.float64) - y_pred.astype(np.float64)) ** 2)))


def baseline_rmse(y: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y.astype(np.float64) - float(y.mean())) ** 2)))


def build_base_model() -> tuple[RidgeRegressor, dict]:
    """Build the initial global model on a small bootstrap corpus."""
    X, y = generate_base_model_data()
    m = RidgeRegressor(alpha=1e-3)
    m.fit(X, y)
    return m, m.to_params()


# ---------------------------------------------------------------------------
# Ship training entry point
# ---------------------------------------------------------------------------

def train_ship(
    ship_id: str,
    base_params: dict,
    key_dir: Path,
    out_dir: Path,
    verbose: bool = True,
) -> Path:
    """Train local model on this ship's sensor slice, sign the delta.

    Returns path to the signed delta JSON file.
    The ship has NO access to other ships' data (DDIL).
    """
    from fleet.signing import (
        build_statement, sign_delta, load_private_key,
        params_hash, data_hash as dhash,
    )
    sys.path.insert(0, str(ROOT))
    from referee.chain import LocalHashChain

    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = SHIP_CONFIGS[ship_id]

    X, y = generate_ship_data(
        range_low_km=cfg["range_low_km"],
        range_high_km=cfg["range_high_km"],
        n=cfg["n_samples"],
        seed=cfg["seed"],
    )

    if verbose:
        print(f"\n{BOLD}[{ship_id}]{END} "
              f"Training on {len(y)} local observations "
              f"(range {cfg['range_low_km']:.0f}–{cfg['range_high_km']:.0f} km, "
              f"DDIL — no cross-ship data access)")

    local_model = RidgeRegressor(alpha=1e-3)
    local_model.fit(X, y)
    local_params = local_model.to_params()

    # Local metrics
    y_pred_train = local_model.predict(X)
    local_train_rmse = rmse(y, y_pred_train)
    local_baseline  = baseline_rmse(y)

    if verbose:
        print(f"  baseline RMSE (mean pred): {local_baseline:.6f}")
        print(f"  local train RMSE         : {local_train_rmse:.6f}")
        print(f"  improvement vs baseline  : {local_baseline - local_train_rmse:+.6f}")

    # Provenance hashes (deterministic, auditable)
    data_repr = [{"ship_id": ship_id, "seed": cfg["seed"],
                  "range_low": cfg["range_low_km"], "range_high": cfg["range_high_km"],
                  "n_samples": cfg["n_samples"]}]
    d_hash    = dhash(data_repr)
    base_hash = params_hash(base_params)

    statement = build_statement(
        ship_id=ship_id,
        data_hash=d_hash,
        base_model_hash=base_hash,
        n_samples=len(y),
        feature_names=FEATURE_NAMES,
        extra={
            "range_low_km": cfg["range_low_km"],
            "range_high_km": cfg["range_high_km"],
            "local_train_rmse": round(local_train_rmse, 6),
            "local_baseline_rmse": round(local_baseline, 6),
        },
    )

    priv_raw = load_private_key(key_dir, ship_id)
    envelope = sign_delta(statement, priv_raw, ship_id)

    delta_pkg = {
        "ship_id": ship_id,
        "envelope": envelope,
        "model_params": local_params,
        "local_hash": params_hash(local_params),
    }
    delta_path = out_dir / f"delta_{ship_id}.json"
    delta_path.write_text(json.dumps(delta_pkg, indent=2))

    # Ship-local chain (audit trail for this ship)
    chain = LocalHashChain()
    chain.append(
        "ship_delta",
        f"{ship_id}_delta",
        json.dumps({
            "ship_id": ship_id,
            "n_samples": len(y),
            "data_hash": d_hash,
            "local_train_rmse": round(local_train_rmse, 6),
            "range_km": f"{cfg['range_low_km']:.0f}..{cfg['range_high_km']:.0f}",
        }).encode(),
    )
    chain.write(out_dir)

    if verbose:
        print(f"  {GREEN}delta signed + chain sealed{END} → {delta_path.relative_to(ROOT)}")
        print(f"  data_hash  : {d_hash[:16]}…")
        print(f"  base_hash  : {base_hash[:16]}…")

    return delta_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS ship node — local training + delta signing")
    ap.add_argument("--ship-id", choices=SHIP_IDS, required=True)
    ap.add_argument("--node-host", default="local",
                    help="'local' or Pi hostname (e.g. pi1.local) — Pi path when reachable")
    ap.add_argument("--plain", action="store_true")
    args = ap.parse_args()

    if args.plain:
        global GREEN, RED, DIM, BOLD, END
        GREEN = RED = DIM = BOLD = END = ""

    print(f"{BOLD}THESEUS Ship Node — {args.ship_id}{END}  (host: {args.node_host})")

    if not (KEYS_DIR / f"{args.ship_id}.key").exists():
        print(f"{RED}ERROR: key not found at {KEYS_DIR}/{args.ship_id}.key{END}")
        print("Run: python -m fleet.fleet_brain --keygen")
        return 1

    _, base_params = build_base_model()
    out_dir = ship_out_dir(args.ship_id)
    train_ship(args.ship_id, base_params, KEYS_DIR, out_dir, verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
