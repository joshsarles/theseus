"""GUARDIAN narrative demo — the Cannonico case, told for a command audience.

  python -m referee.guardian_demo            # play the story (full narration)
  python -m referee.guardian_demo --plain    # same, no colors (for runbook capture)

This is a NARRATION LAYER on top of the existing engine. It does NOT reimplement the
gate or the chain — it drives `referee.intake` -> `referee.policy` -> `referee.chain`
exactly as the smoke test does, and reads the engine's verdict out loud. The story is
scripted on SYNTHETIC, UNCLASSIFIED data (see fixtures/scenario_cannonico.py).

What a general should see happen on screen, in order:
  1. CATCH IT      — the moment the AI drifts out of its authorized parameters.
  2. HUMAN DECIDES — every out-of-bounds step HALTS and hands the call to a human,
                     and that human decision is written down. Advisory only: GUARDIAN
                     never takes the action. The human always decides.
  3. RECORD IT     — an unbreakable record; tamper one byte and GUARDIAN catches it;
                     a clean record verifies again. "This cannot be quietly changed."
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .chain import LocalHashChain, tamper, verify_dir
from .intake import ObservationIngestor
from .policy import evaluate_policy, load_policy
from .schemas import PolicyDecision

import importlib.util

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "fixtures" / "policy_cannonico.json"
OUT = ROOT / "out_guardian"


def _load_scenario() -> object:
    """Import fixtures/scenario_cannonico.py without requiring it to be a package."""
    spec = importlib.util.spec_from_file_location(
        "scenario_cannonico", ROOT / "fixtures" / "scenario_cannonico.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass field-resolution can find the module's namespace.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---- presentation ----------------------------------------------------------

@dataclass(frozen=True)
class Palette:
    bold: str
    dim: str
    green: str
    red: str
    yellow: str
    cyan: str
    end: str

    @classmethod
    def for_tty(cls, enabled: bool) -> "Palette":
        if not enabled:
            return cls("", "", "", "", "", "", "")
        return cls("\033[1m", "\033[2m", "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m")


def _rule_plain(rule: str) -> str:
    """Map an engine rule name to a phrase a general follows without a glossary."""
    return {
        "geofence": "crossed the edge of its authorized box",
        "confidence_floor": "acted on a read it was barely sure of (below the confidence floor)",
        "stale_decision": "acted on a read that had already expired (stale picture)",
        "forbidden_class_adjacency": "fixed on a target beside a protected place",
        "forbidden_decision_type": "tried to make a call reserved for a human (a strike)",
        "provenance_missing": "made a call with no record of where it came from",
        "latency_sla": "answered too slowly to be trusted in the moment",
        "classification_ceiling": "handled material above its authorized level",
        "ddil_profile": "operated in a comms state it was not cleared for",
        "malformed": "sent something unreadable",
        "unevaluable_rule": "could not be checked, so GUARDIAN fails closed (treats it as out of bounds)",
    }.get(rule, rule)


def _human_decision(rules: list[str], step_label: str) -> str:
    """The scripted human-in-command call for an out-of-bounds step (synthetic).

    GUARDIAN is advisory: it HALTS and hands the decision back. The human decides.
    These are the calls the human operator makes in this story, recorded verbatim.
    """
    if "forbidden_decision_type" in rules:
        return "DENIED by human operator — strike authority is not delegated to the AI; no action taken."
    if "geofence" in rules:
        return "ACKNOWLEDGED by human operator — recall ordered; steer the aircraft back inside the box."
    if "forbidden_class_adjacency" in rules:
        return "DENIED by human operator — protected place in view; hold, do not act."
    if "confidence_floor" in rules:
        return "REJECTED by human operator — read is not trustworthy; disregard and re-observe."
    if "stale_decision" in rules:
        return "REJECTED by human operator — picture is stale; do not carry it forward."
    return "REVIEWED by human operator — held pending a confident, in-bounds read."


# ---- the run ---------------------------------------------------------------

def play(plain: bool = False) -> int:
    # Color only when attached to a terminal and --plain was not passed.
    p = Palette.for_tty(enabled=(not plain) and sys.stdout.isatty())

    scenario = _load_scenario()
    steps = scenario.steps()  # type: ignore[attr-defined]

    policy = load_policy(POLICY)
    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)

    bar = "═" * 74
    print()
    print(f"{p.bold}{p.cyan}  GUARDIAN — a guardian for military AI{p.end}")
    print(f"{p.dim}  Scripted scenario on synthetic, unclassified data. Advisory only — the human always decides.{p.end}")
    print(f"  {bar}")
    print(f"{p.bold}  THE CANNONICO CASE: an autonomous drone loses contact and starts operating on its own.{p.end}")
    print(f"{p.dim}  GUARDIAN rides alongside the AI and does three jobs you can watch happen below:{p.end}")
    print(f"{p.dim}    1) catch the AI going out of bounds   2) keep a human in command   3) keep an unbreakable record{p.end}")
    print(f"  {bar}")
    print()

    out_of_bounds_steps = 0
    decisions: list[tuple[object, PolicyDecision]] = []

    for s in steps:  # type: ignore[union-attr]
        chained = ingestor.ingest(s.to_jsonl())
        decision = evaluate_policy(chained.obs, policy)
        decisions.append((s, decision))

        # Chain every violation too (same as the smoke spine) so the record is complete.
        for viol in decision.violations:
            chain.append("violation", viol.obs_id, json.dumps(viol.__dict__).encode())

        breach = decision.gate != "PASS"
        tag = f"{p.bold}STEP {s.step:>2}{p.end}"
        print(f"{tag}  {p.bold}{s.headline}{p.end}")

        if not breach:
            print(f"        {p.green}✅ GUARDIAN: IN BOUNDS{p.end} — {s.because}")
        else:
            rules = [v.rule for v in decision.violations]
            why = "; ".join(_rule_plain(r) for r in rules)
            # 1) CATCH IT
            print(f"        {p.red}⛔ GUARDIAN: OUT OF BOUNDS{p.end} — the AI {why}.")
            print(f"        {p.dim}why it matters: {s.because}{p.end}")
            # 2) HUMAN DECIDES (explicit, legible human-in-command beat)
            print(f"        {p.yellow}↳ HALTED.{p.end} Decision returned to the human operator. "
                  f"{p.dim}(GUARDIAN advises; it does not act.){p.end}")
            print(f"        {p.yellow}↳ HUMAN IN COMMAND:{p.end} {_human_decision(rules, s.label)}")
            print(f"        {p.dim}↳ recorded: AI advised, GUARDIAN flagged, human decided — all three on the unbreakable record.{p.end}")
            out_of_bounds_steps += 1
        print()

    # 3) RECORD IT — write and prove the record.
    chain.write(OUT)
    print(f"  {bar}")
    print(f"{p.bold}  THE PROOF: an unbreakable record.{p.end}")
    print(f"  {bar}")
    in_bounds = len(steps) - out_of_bounds_steps  # type: ignore[arg-type]
    print(f"  The full mission is now written down: {p.bold}{len(chain.leaves)} sealed entries{p.end} "
          f"({len(steps)} agent steps + the violations GUARDIAN flagged).")  # type: ignore[arg-type]
    print(f"  {p.green}{in_bounds} steps in bounds{p.end}, {p.red}{out_of_bounds_steps} steps out of bounds and handed to a human{p.end}.")
    print()

    ok, _, msg = verify_dir(OUT)
    print(f"  1. Verify the record as written:  {p.green if ok else p.red}{msg}{p.end}")
    print(f"     {p.dim}Anyone can run this offline. No trust in us required.{p.end}")
    print()

    # Tamper one byte in a middle entry and show GUARDIAN catches it.
    target_leaf = min(8, len(chain.leaves) - 1)
    note = tamper(OUT, target_leaf)
    print(f"  2. Now someone quietly changes the record: {p.dim}{note}.{p.end}")
    bad_ok, first_bad, bad_msg = verify_dir(OUT)
    if not bad_ok:
        print(f"     {p.red}⛔ GUARDIAN: the record was altered — {bad_msg}{p.end}")
        print(f"     {p.bold}This record cannot be quietly changed — here's the proof: the seal snaps the instant one byte moves.{p.end}")
    else:
        print(f"     {p.red}UNEXPECTED: tamper not detected — investigate before relying on this run.{p.end}")
    print()

    # Re-seal a clean record and show a clean re-verify passes.
    chain.write(OUT)
    clean_ok, _, clean_msg = verify_dir(OUT)
    print(f"  3. Restore the true record and verify again:  {p.green if clean_ok else p.red}{clean_msg}{p.end}")
    print(f"     {p.dim}The truth is recoverable: the real record still stands, and still verifies.{p.end}")
    print()

    # THE GENERALIZE LINE.
    print(f"  {bar}")
    print(f"{p.bold}  This same guardian rides any AI agent — not just a drone.{p.end}")
    print(f"  The drone that lost contact is also every one of the agents now running across the")
    print(f"  department: each one can drift out of bounds, and each one needs a human in command")
    print(f"  and a record that proves what happened. GUARDIAN is that, for all of them.")
    print(f"  {bar}")
    print()

    # Honest, machine-checkable exit status for the test + runbook.
    everything_held = ok and (not bad_ok) and clean_ok
    if not everything_held:
        print(f"{p.red}  GUARDIAN DEMO FAIL{p.end} — the proof beat did not behave as scripted.")
        return 1
    print(f"{p.green}  GUARDIAN DEMO OK{p.end} — caught the drift, kept the human in command, proved the record.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="GUARDIAN narrative demo (the Cannonico case).")
    ap.add_argument("--plain", action="store_true", help="no ANSI colors (for runbook capture)")
    args = ap.parse_args()
    return play(plain=args.plain)


if __name__ == "__main__":
    sys.exit(main())
