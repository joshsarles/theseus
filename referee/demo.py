"""Scenario driver + CLI.

  python -m referee.demo --smoke            # spine run over fixtures/smoke_25.jsonl + assertions
  python -m referee.demo --verify           # offline verification of out/
  python -m referee.demo --tamper 9         # flip one byte in leaf 9 (then --verify snaps red)
  python -m referee.demo --scenario cannonico --speed 8x --smoke   # spec §3.3 one-command form
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .aiir import emit_incident_records
from .chain import LocalHashChain, tamper, verify_dir
from .intake import ObservationIngestor, jsonl_replay
from .policy import evaluate_policy, load_policy

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "smoke_25.jsonl"
POLICY = ROOT / "fixtures" / "policy_cannonico.json"
OUT = ROOT / "out"

GREEN, RED, DIM, END = "\033[92m", "\033[91m", "\033[2m", "\033[0m"


def _parse_speed(value: str) -> float:
    """'8x' -> 8.0 — replay-pacing multiplier (1x = baseline)."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)x", value.strip().lower())
    if not m or float(m.group(1)) <= 0:
        raise argparse.ArgumentTypeError(f"expected a speed like '1x' or '8x', got {value!r}")
    return float(m.group(1))


def run_smoke(assert_expected: bool = True, policy_path: Path = POLICY,
              speed: float = 1.0) -> int:
    # speed: pacing multiplier for live/timed replay; the offline fixture replay
    # below is instant, so pacing is a no-op here (flag parsed for §3.3 parity).
    policy = load_policy(policy_path)
    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)

    decisions = []
    breaches = []  # (obs, decision, violation, violation_leaf) — AIIR: one record per BREACH
    for raw in jsonl_replay(FIXTURE):
        chained = ingestor.ingest(raw)
        decision = evaluate_policy(chained.obs, policy)
        for viol in decision.violations:  # violations are chained too
            vleaf = chain.append("violation", viol.obs_id, json.dumps(viol.__dict__).encode())
            if viol.severity == "BREACH":
                breaches.append((chained.obs, decision, viol, vleaf))
        decisions.append((chained, decision))
        mark = f"{RED}HALT{END}" if decision.gate != "PASS" else f"{GREEN}pass{END}"
        rules = ",".join(v.rule for v in decision.violations) or "-"
        print(f"  leaf {chained.leaf.idx:>2}  {chained.obs.source_model_id:<12} "
              f"{chained.obs.decision_type:<10} {mark}  {DIM}{rules}{END}")

    chain.write(OUT)
    sev = Counter(v.severity for _, d in decisions for v in d.violations)
    obs_count = len(decisions)
    leaf_count = len(chain.leaves)
    print(f"\n  observations={obs_count}  chain_leaves={leaf_count} "
          f"(obs + {leaf_count - obs_count} violation leaves)")
    print(f"  violations: BREACH={sev.get('BREACH', 0)}  WARN={sev.get('WARN', 0)}")
    ok, first_bad, msg = verify_dir(OUT)
    print(f"  verify: {(GREEN if ok else RED)}{msg}{END}")

    # AIIR v0.1 side artifacts: one incident record per BREACH (never chained,
    # never part of verify/tamper). Structural check = stdlib subset vs vendored schema.
    aiir_paths, aiir_errors = emit_incident_records(
        breaches, chain=chain, policy=policy, policy_path=policy_path,
        out_dir=OUT / "incident_records",
        verify_status="PASS" if ok else "FAIL", verify_message=msg,
        verify_first_bad_leaf=first_bad,
    )
    aiir_ok = not aiir_errors
    print(f"  incident records: {len(aiir_paths)} AIIR v0.1 -> out/incident_records/ "
          f"(structural schema check: {(GREEN + 'OK' + END) if aiir_ok else (RED + 'FAIL' + END)})")
    for err in aiir_errors:
        print(f"    {RED}aiir schema error{END} {err}")

    if assert_expected:
        expected = {"obs": 25, "breach": 4, "warn": 4, "verify": True,
                    "aiir": 4, "aiir_schema_ok": True}
        actual = {"obs": obs_count, "breach": sev.get("BREACH", 0),
                  "warn": sev.get("WARN", 0), "verify": ok,
                  "aiir": len(aiir_paths), "aiir_schema_ok": aiir_ok}
        if actual != expected:
            print(f"{RED}SMOKE FAIL{END} expected={expected} actual={actual}")
            return 1
        print(f"{GREEN}SMOKE GREEN{END} — spine (intake → gate → chain → bundle → verify) holds.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-assert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--tamper", type=int, default=None, metavar="LEAF")
    ap.add_argument("--scenario", default="cannonico", metavar="NAME",
                    help="policy fixture to load: fixtures/policy_<NAME>.json (default: cannonico)")
    ap.add_argument("--speed", type=_parse_speed, default="1x", metavar="NX",
                    help="replay-pacing multiplier like 8x (no-op for offline fixture replay)")
    args = ap.parse_args()

    if args.smoke:
        policy_path = ROOT / "fixtures" / f"policy_{args.scenario}.json"
        if not policy_path.is_file():
            print(f"{RED}unknown scenario {args.scenario!r}{END} — no fixture at {policy_path}")
            return 2
        return run_smoke(assert_expected=not args.no_assert,
                         policy_path=policy_path, speed=args.speed)
    if args.tamper is not None:
        print(tamper(OUT, args.tamper))
        return 0
    if args.verify:
        ok, _, msg = verify_dir(OUT)
        print(f"{(GREEN if ok else RED)}{msg}{END}")
        return 0 if ok else 2
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
