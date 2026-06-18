"""THESEUS Fleet-Learning Miniature — Fleet Brain.

Responsibilities:
  1. KEY GENERATION (--keygen): generate Ed25519 keypairs for all ships.
  2. DELTA COLLECTION: load signed delta packages from each ship's output dir.
  3. PROVENANCE GATE: verify every delta's DSSE envelope against the known ship key.
     A delta with a forged/absent/tampered attestation is REJECTED and sealed as
     fleet_merge_rejected in the fleet chain.
  4. FEDAVG MERGE: average model parameters across all ACCEPTED deltas, weighted
     equally (FedAvg). If deltas have heterogeneous sample counts, weight by n_samples.
  5. EVAL GATE: merged model must beat the incumbent on a held-out set before acceptance.
     If it regresses on RMSE, REJECT + keep last-good (rollback). This defeats
     catastrophic forgetting.
  6. ACCEPT/REJECT: seal fleet_merge_accepted or fleet_merge_rejected in the chain.
  7. MODEL PUSH: write the improved model params back as fleet_model.json for ships.

The fleet chain is the authoritative record of every merge decision.
It lives at fleet/out/fleet_record/ (separate from individual ship chains).

Poison injection: --inject-poison writes a delta with a FORGED signature (wrong key).
The fleet brain rejects it and seals fleet_merge_rejected. This is the live demo beat.
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
FLEET_RECORD_DIR = FLEET_DIR / "out" / "fleet_record"

SHIP_IDS = ["MACHINERY", "CONTACTS"]
GREEN, RED, DIM, BOLD, CYAN, YELLOW, END = (
    "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[96m", "\033[93m", "\033[0m"
)
BAR = "═" * 72


def ship_out_dir(ship_id: str) -> Path:
    return FLEET_DIR / "out" / ship_id


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def keygen() -> None:
    from fleet.signing import generate_keypair
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    for sid in SHIP_IDS:
        priv, pub = generate_keypair(KEYS_DIR, sid)
        print(f"  {GREEN}keygen{END} {sid}: priv={len(priv)}B  pub={len(pub)}B  → {KEYS_DIR}/")
    print(f"  {DIM}(private keys stay on each ship; .pub files are the fleet brain's trust roots){END}")


# ---------------------------------------------------------------------------
# Model param helpers (mirror ship_node.RidgeRegressor without import cycle)
# ---------------------------------------------------------------------------

class _Ridge:
    """Minimal Ridge wrapper for fleet-brain operations (load/predict only)."""
    def __init__(self, params: dict):
        self.coef_ = np.array(params["coef"], dtype=np.float64)
        self.intercept_ = float(params["intercept"])
        self.alpha = float(params.get("alpha", 1e-3))
        self.n_features_ = int(params["n_features"])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (X.astype(np.float64) @ self.coef_ + self.intercept_).astype(np.float32)

    def to_params(self) -> dict:
        return {
            "coef": self.coef_.tolist(),
            "intercept": self.intercept_,
            "alpha": self.alpha,
            "n_features": self.n_features_,
        }


def fedavg(param_list: list[dict], weights: list[float]) -> dict:
    """FedAvg: weighted average of model params.

    weights should be unnormalized (e.g. n_samples per ship); normalized internally.
    """
    total = sum(weights)
    norm_w = [w / total for w in weights]
    n = len(param_list)
    assert n > 0

    merged_coef = sum(
        np.array(p["coef"]) * w for p, w in zip(param_list, norm_w)
    )
    merged_intercept = sum(p["intercept"] * w for p, w in zip(param_list, norm_w))

    return {
        "coef": merged_coef.tolist(),
        "intercept": float(merged_intercept),
        "alpha": param_list[0]["alpha"],
        "n_features": param_list[0]["n_features"],
    }


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


# ---------------------------------------------------------------------------
# Held-out evaluation set (fleet brain owns this; ships never see it)
# ---------------------------------------------------------------------------

def load_held_out() -> tuple[np.ndarray, np.ndarray]:
    """Fleet brain's held-out eval set — full range (0–25 km), ships never see this.

    Deterministic: seed=42. Covers BOTH ship range strata so evaluation is global.
    """
    sys.path.insert(0, str(ROOT))
    from fleet.ship_node import generate_fleet_held_out
    return generate_fleet_held_out(n=150, seed=42)


# ---------------------------------------------------------------------------
# Poison injection
# ---------------------------------------------------------------------------

def inject_poison(poison_ship_id: str = "POISON_NODE") -> Path:
    """Write a delta package signed with a fresh (unknown) key — simulates poisoning."""
    from fleet.signing import generate_keypair, build_statement, sign_delta, params_hash
    import tempfile, time

    print(f"\n{YELLOW}[POISON INJECTION]{END} Generating forged delta signed with unknown key…")

    # Generate a key that is NOT registered in KEYS_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        priv_raw, _ = generate_keypair(tmp_path, poison_ship_id)

        # Build a plausible-looking model (garbage weights)
        np.random.seed(42)
        fake_params = {
            "coef": [0.99, 0.01, 0.01, 0.01, 0.01],
            "intercept": 0.5,
            "alpha": 1e-3,
            "n_features": 5,
        }
        statement = build_statement(
            ship_id=poison_ship_id,
            data_hash="deadbeef" * 8,
            base_model_hash="cafebabe" * 8,
            n_samples=999,
            feature_names=["range_n", "bearing_sin", "bearing_cos", "signal_n", "doppler_n"],
            extra={"note": "POISONED DELTA — forged signature from unregistered ship"},
        )
        envelope = sign_delta(statement, priv_raw, poison_ship_id)

    poison_pkg = {
        "ship_id": poison_ship_id,
        "envelope": envelope,
        "model_params": fake_params,
        "local_hash": params_hash(fake_params),
    }

    poison_path = FLEET_DIR / "out" / f"delta_{poison_ship_id}.json"
    poison_path.parent.mkdir(parents=True, exist_ok=True)
    poison_path.write_text(json.dumps(poison_pkg, indent=2))
    print(f"  {YELLOW}poisoned delta written{END} → {poison_path.relative_to(ROOT)}")
    print(f"  {DIM}(signed by unregistered key — fleet brain should REJECT this){END}")
    return poison_path


# ---------------------------------------------------------------------------
# Main merge loop
# ---------------------------------------------------------------------------

def _seal_fleet_leaf(out_dir: Path, kind: str, obs_id: str, record: dict) -> None:
    """Seal one leaf into the fleet chain using the proven reload+append+write pattern.

    Mirrors demo/_record.py::seal(): reloads the chain from disk, appends exactly ONE
    leaf, then writes atomically. This ensures each leaf's record_b64 is always written
    from the same data used to compute its hash — no accumulation of in-memory state
    across multiple appends before a single write.
    """
    from referee.chain import Leaf, LocalHashChain
    out_dir.mkdir(parents=True, exist_ok=True)
    chain = LocalHashChain()
    cp = out_dir / "chain.jsonl"
    if cp.exists():
        for line in cp.read_text().splitlines():
            if line.strip():
                chain.leaves.append(Leaf(**json.loads(line)))
    chain.append(kind, obs_id, json.dumps(record, sort_keys=True).encode())
    chain.write(out_dir)


def run_merge(
    delta_paths: list[Path],
    incumbent_params_path: Path | None,
    verbose: bool = True,
) -> tuple[bool, dict, dict]:
    """Run the full provenance-gate + eval-gate merge.

    Returns (accepted: bool, merged_params: dict, report: dict).
    The report contains all metric values (honest numbers for the demo).
    """
    sys.path.insert(0, str(ROOT))
    from fleet.signing import verify_envelope
    from referee.chain import verify_dir

    FLEET_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "deltas_submitted": len(delta_paths),
        "deltas_accepted": 0,
        "deltas_rejected": 0,
        "rejected_details": [],
        "accepted_ships": [],
        "fedavg_weights": [],
    }

    accepted_params: list[dict] = []
    accepted_weights: list[float] = []

    if verbose:
        print(f"\n{BOLD}{CYAN}  FLEET BRAIN — PROVENANCE GATE{END}")
        print(f"  {DIM}Verifying {len(delta_paths)} submitted delta(s)…{END}")

    for dp in delta_paths:
        if not dp.exists():
            print(f"  {RED}SKIP{END} {dp.name} — file not found")
            continue

        pkg = json.loads(dp.read_text())
        ship_id = pkg.get("ship_id", "UNKNOWN")
        envelope = pkg.get("envelope", {})
        model_params = pkg.get("model_params", {})

        ok, reason, statement = verify_envelope(envelope, KEYS_DIR)

        if verbose:
            status = f"{GREEN}ACCEPTED{END}" if ok else f"{RED}REJECTED{END}"
            print(f"  [{ship_id:>14}]  {status}  {DIM}{reason}{END}")

        if ok:
            n_samples = statement["predicate"]["n_samples"]
            accepted_params.append(model_params)
            accepted_weights.append(float(n_samples))
            report["deltas_accepted"] += 1
            report["accepted_ships"].append(ship_id)
            report["fedavg_weights"].append(n_samples)

            _seal_fleet_leaf(
                FLEET_RECORD_DIR,
                "fleet_delta_accepted",
                f"{ship_id}_accepted",
                {
                    "ship_id": ship_id,
                    "data_hash": statement["subject"]["data_hash"],
                    "n_samples": n_samples,
                    "local_train_rmse": statement["predicate"].get("local_train_rmse"),
                },
            )
        else:
            report["deltas_rejected"] += 1
            report["rejected_details"].append({"ship_id": ship_id, "reason": reason})

            _seal_fleet_leaf(
                FLEET_RECORD_DIR,
                "fleet_merge_rejected",
                f"{ship_id}_rejected",
                {
                    "ship_id": ship_id,
                    "reason": reason,
                    "envelope_keyid": (
                        envelope.get("signatures", [{}])[0].get("keyid", "?")
                        if envelope.get("signatures") else "none"
                    ),
                },
            )

    if not accepted_params:
        if verbose:
            print(f"\n  {RED}No valid deltas — aborting merge.{END}")
        report["outcome"] = "aborted_no_valid_deltas"
        return False, {}, report

    # FedAvg merge
    if verbose:
        print(f"\n{BOLD}{CYAN}  FLEET BRAIN — FEDAVG MERGE{END}")
        print(f"  Merging {len(accepted_params)} accepted delta(s) "
              f"(weights by n_samples: {accepted_weights})")

    merged_params = fedavg(accepted_params, accepted_weights)

    # EVAL GATE: compare merged vs incumbent on held-out set
    X_held, y_held = load_held_out()

    merged_model = _Ridge(merged_params)
    merged_pred = merged_model.predict(X_held)
    merged_rmse = rmse(y_held, merged_pred)

    if incumbent_params_path and incumbent_params_path.exists():
        incumbent_params = json.loads(incumbent_params_path.read_text())
        incumbent_model = _Ridge(incumbent_params)
        incumbent_pred = incumbent_model.predict(X_held)
        incumbent_rmse = rmse(y_held, incumbent_pred)
        have_incumbent = True
    else:
        # Cold start: use the base model (trained on small bootstrap corpus) as incumbent.
        # This is what the fleet brain had BEFORE the ships reported back.
        from fleet.ship_node import build_base_model as _build_base
        _, base_params = _build_base()
        incumbent_model = _Ridge(base_params)
        incumbent_pred = incumbent_model.predict(X_held)
        incumbent_rmse = rmse(y_held, incumbent_pred)
        have_incumbent = False

    rmse_delta = merged_rmse - incumbent_rmse  # negative = improvement
    eval_passed = merged_rmse < incumbent_rmse

    report["held_out_n"] = int(len(y_held))
    report["incumbent_rmse"] = round(incumbent_rmse, 6)
    report["merged_rmse"] = round(merged_rmse, 6)
    report["rmse_delta"] = round(rmse_delta, 6)
    report["eval_gate_passed"] = eval_passed
    report["incumbent_source"] = "previous_fleet_model" if have_incumbent else "base_model_bootstrap"

    if verbose:
        print(f"  Held-out n={len(y_held)}")
        incumbent_label = "prev fleet model" if have_incumbent else "base model (50-sample bootstrap)"
        print(f"  Incumbent RMSE ({incumbent_label}): {incumbent_rmse:.6f}")
        print(f"  Merged RMSE                       : {merged_rmse:.6f}")
        delta_str = f"{rmse_delta:+.6f}"
        color = GREEN if eval_passed else RED
        print(f"  RMSE delta (merged - incumbent)   : {color}{delta_str}{END}")

    if eval_passed:
        if verbose:
            print(f"\n  {GREEN}EVAL GATE: PASS{END} — merged model improves on held-out set. Accepting.")
        _seal_fleet_leaf(
            FLEET_RECORD_DIR,
            "fleet_merge_accepted",
            "fleet_merge",
            {
                "accepted_ships": report["accepted_ships"],
                "fedavg_weights": report["fedavg_weights"],
                "incumbent_rmse": report["incumbent_rmse"],
                "merged_rmse": report["merged_rmse"],
                "rmse_delta": report["rmse_delta"],
                "held_out_n": report["held_out_n"],
            },
        )
        report["outcome"] = "accepted"
    else:
        if verbose:
            print(f"\n  {RED}EVAL GATE: FAIL{END} — merged model regresses. Rolling back to incumbent.")
        _seal_fleet_leaf(
            FLEET_RECORD_DIR,
            "fleet_merge_rejected",
            "eval_gate_fail",
            {
                "reason": "eval_gate_regression",
                "incumbent_rmse": report["incumbent_rmse"],
                "merged_rmse": report["merged_rmse"],
                "rmse_delta": report["rmse_delta"],
            },
        )
        report["outcome"] = "eval_gate_rollback"

    ok_verify, _, verify_msg = verify_dir(FLEET_RECORD_DIR)
    report["chain_verify"] = ok_verify
    report["chain_verify_msg"] = verify_msg

    if verbose:
        verify_color = GREEN if ok_verify else RED
        print(f"\n  {BOLD}Chain verify{END}: {verify_color}{verify_msg}{END}")

    return eval_passed, merged_params, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    global GREEN, RED, DIM, BOLD, CYAN, YELLOW, END
    global FLEET_RECORD_DIR

    ap = argparse.ArgumentParser(description="THESEUS fleet brain — merge + eval-gate + sign")
    ap.add_argument("--keygen", action="store_true",
                    help="Generate Ed25519 keypairs for all ships")
    ap.add_argument("--merge", action="store_true",
                    help="Collect deltas from ship output dirs and run merge")
    ap.add_argument("--inject-poison", action="store_true",
                    help="Inject a forged delta (wrong key) to demo poisoning defense")
    ap.add_argument("--plain", action="store_true", help="No ANSI colors")
    ap.add_argument("--record", default=str(FLEET_RECORD_DIR),
                    help="Fleet chain record dir (default: fleet/out/fleet_record)")
    args = ap.parse_args()

    if args.plain:
        GREEN = RED = DIM = BOLD = CYAN = YELLOW = END = ""

    FLEET_RECORD_DIR = Path(args.record)

    if args.keygen:
        print(f"{BOLD}THESEUS Fleet Brain — Key Generation{END}")
        keygen()
        return 0

    if args.inject_poison:
        inject_poison()
        return 0

    if args.merge:
        print(f"{BOLD}THESEUS Fleet Brain — Merge{END}")
        delta_paths = [ship_out_dir(sid) / f"delta_{sid}.json" for sid in SHIP_IDS]
        # Also pick up any poison deltas
        for p in (FLEET_DIR / "out").glob("delta_POISON*.json"):
            delta_paths.append(p)

        incumbent_path = FLEET_DIR / "out" / "fleet_record" / "fleet_model.json"
        accepted, merged_params, report = run_merge(delta_paths, incumbent_path)

        if accepted:
            out_model = FLEET_RECORD_DIR / "fleet_model.json"
            out_model.write_text(json.dumps(merged_params, indent=2))
            print(f"\n  {GREEN}Fleet model written{END} → {out_model.relative_to(ROOT)}")

        out_report = FLEET_RECORD_DIR / "merge_report.json"
        out_report.write_text(json.dumps(report, indent=2))
        print(f"  Report → {out_report.relative_to(ROOT)}")
        return 0 if accepted else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
