"""APPRENTICE narrative demo — an analyst works, an apprentice learns by watching.

  python -m referee.apprentice_demo            # play the story (full narration)
  python -m referee.apprentice_demo --plain    # same, no colors (for runbook capture)

This is a NARRATION LAYER on top of the existing engine. It does NOT reimplement the
chain or the gate. It drives `referee.intake` -> `referee.policy` -> `referee.chain`
exactly as the smoke test does, and tells the Apprentice Layer story over the engine's
real verdicts.

What the engine really does here:
  - CAPTURE + PROVENANCE SPINE: every analyst decision is recorded, signed, and
    hash-chained the instant it happens, at zero added operator time. (Real.)
  - HANDBACK ROUTER: the gate decides which calls are clean, in-class lessons the
    apprentice may learn from, and which are hard cases handed straight back to the
    human (below the confidence floor, beside a protected class, no provenance). (Real.)
  - TAMPER-EVIDENCE: change one byte of the record and it snaps; restore it and it
    verifies again. (Real.)

What is SCRIPTED illustration on synthetic data, stated on screen:
  - the "apprentice suggests / drafts the call it watched" beats. There is no trained
    model in this demo. The real apprentice trains on the captured corpus in the pilot.

Three things a room should see happen, in order:
  1. WATCH       — the apprentice records the work already happening; effort is the
                   signal, a half-second accept is the noise. Zero added operator time.
  2. LEARN+SUGGEST (scripted) — on the easy class it watched, it offers an ignorable
                   suggestion; the human confirms. The human still makes the call.
  3. HAND BACK   — a hard case arrives; the apprentice does not touch it; it hands it
                   back to the human, who decides. The apprentice never acts.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .chain import LocalHashChain, tamper, verify_dir
from .intake import ObservationIngestor
from .policy import evaluate_policy, load_policy

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "fixtures" / "policy_cannonico.json"  # reused: confidence floor, protected class, provenance
OUT = ROOT / "out_apprentice"


def _load_scenario() -> object:
    spec = importlib.util.spec_from_file_location(
        "scenario_apprentice", ROOT / "fixtures" / "scenario_apprentice.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


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


_EFFORT = {
    "high": "HIGH weight  (the analyst worked this; this is the lesson)",
    "med": "some weight  (the analyst paused on this)",
    "low": "near-zero weight  (a half-second clear; speed is the noise)",
}


def play(plain: bool = False) -> int:
    p = Palette.for_tty(enabled=(not plain) and sys.stdout.isatty())

    scenario = _load_scenario()
    steps = scenario.steps()  # type: ignore[attr-defined]

    policy = load_policy(POLICY)
    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)

    bar = "═" * 78
    print()
    print(f"{p.bold}{p.cyan}  THE APPRENTICE — a workforce that multiplies itself{p.end}")
    print(f"{p.dim}  Scripted scenario on synthetic, unclassified data. The apprentice never acts. The human always decides.{p.end}")
    print(f"  {bar}")
    print(f"{p.bold}  An imagery analyst works a queue. An apprentice sits beside them and watches.{p.end}")
    print(f"{p.dim}  It adds nothing to the screen and asks nothing of the analyst. It learns the craft from the{p.end}")
    print(f"{p.dim}  work already happening, then takes the toil and hands the hard call back. Watch three things:{p.end}")
    print(f"{p.dim}    1) WATCH the work (zero added time)   2) LEARN + SUGGEST the easy class   3) HAND the hard case BACK{p.end}")
    print(f"  {bar}")
    print()

    learnable = 0
    handbacks = 0
    apprentice_actions = 0  # must stay 0: the apprentice suggests/drafts, the human confirms
    story_aligned = True

    for s in steps:  # type: ignore[union-attr]
        chained = ingestor.ingest(s.to_jsonl())
        decision = evaluate_policy(chained.obs, policy)
        # Chain the gate outcome too, so the record is complete (same as the smoke spine).
        for viol in decision.violations:
            chain.append("handback", viol.obs_id, json.dumps(viol.__dict__).encode())

        is_hard = decision.gate != "PASS"
        # The engine is the judge; the scenario's `expect` is only the author's intent.
        if (is_hard and s.expect != "handback") or ((not is_hard) and s.expect != "learnable"):
            story_aligned = False

        print(f"{p.bold}STEP {s.step:>2}{p.end}  {p.bold}{s.headline}{p.end}")
        print(f"        {p.dim}analyst: {s.analyst_call}{p.end}")

        if not is_hard:
            learnable += 1
            # Capture is real; the suggest/draft beats are scripted illustration.
            print(f"        {p.green}captured{p.end} into the signed record at zero added operator time.")
            print(f"        {p.dim}apprentice weight: {_EFFORT.get(s.effort, s.effort)}{p.end}")
            if s.role == "watch":
                print(f"        {p.cyan}↳ the apprentice WATCHES and logs this lesson.{p.end} It acts on nothing.")
            elif s.role == "suggest":
                print(f"        {p.cyan}↳ the apprentice SUGGESTS the call it watched{p.end} {p.dim}(scripted illustration; no trained model in this demo).{p.end}")
                print(f"        {p.yellow}↳ HUMAN IN COMMAND:{p.end} the analyst confirmed. Nothing enters the product unless the human acts.")
            elif s.role == "draft":
                print(f"        {p.cyan}↳ the apprentice DRAFTS the routine calls{p.end} {p.dim}(scripted illustration).{p.end} {p.yellow}The human confirms each one.{p.end}")
        else:
            handbacks += 1
            rules = "; ".join(v.rule for v in decision.violations)
            print(f"        {p.red}⛔ HARD CASE{p.end} ({rules}). {p.bold}The apprentice does not touch it.{p.end}")
            print(f"        {p.yellow}↳ HANDED BACK to the human.{p.end} {s.because.split('.')[0]}.")
            print(f"        {p.yellow}↳ HUMAN DECIDES:{p.end} {s.analyst_call}")
        print()

    chain.write(OUT)

    print(f"  {bar}")
    print(f"{p.bold}  THE PROOF{p.end}")
    print(f"  {bar}")
    print(f"  The whole shift is written down: {p.bold}{len(chain.leaves)} sealed entries{p.end} "
          f"({len(steps)} analyst decisions + the hard cases the apprentice handed back).")  # type: ignore[arg-type]
    print(f"  {p.green}{learnable} clean, in-class lessons captured{p.end}, "
          f"{p.red}{handbacks} hard cases handed back to a human{p.end}, "
          f"{p.bold}{apprentice_actions} actions taken by the apprentice{p.end}.")
    print(f"  {p.dim}Zero added operator time: capture is passive. The analyst worked their normal queue; the watching was the only new thing.{p.end}")
    print(f"  {p.dim}Human in command: every call on the record is the analyst's. The apprentice suggested at most; it never decided.{p.end}")
    print()

    ok, _, msg = verify_dir(OUT)
    print(f"  1. Verify the record as written:  {p.green if ok else p.red}{msg}{p.end}")
    print(f"     {p.dim}Anyone can run this offline. Every lesson carries who decided it, when, and on what evidence (provenance).{p.end}")
    print()

    target_leaf = min(8, len(chain.leaves) - 1)
    note = tamper(OUT, target_leaf)
    print(f"  2. Someone quietly changes the record: {p.dim}{note}.{p.end}")
    bad_ok, _, bad_msg = verify_dir(OUT)
    if not bad_ok:
        print(f"     {p.red}⛔ the record was altered — {bad_msg}{p.end}")
        print(f"     {p.bold}The training signal cannot be quietly forged: the seal snaps the instant one byte moves.{p.end}")
    else:
        print(f"     {p.red}UNEXPECTED: tamper not detected — investigate before relying on this run.{p.end}")
    print()

    chain.write(OUT)
    clean_ok, _, clean_msg = verify_dir(OUT)
    print(f"  3. Restore the true record and verify again:  {p.green if clean_ok else p.red}{clean_msg}{p.end}")
    print()

    print(f"  {bar}")
    print(f"{p.bold}  This same apprentice rides every operator. The work is the curriculum.{p.end}")
    print(f"  The analyst's judgment used to die the instant it was made. Now it is captured for free as")
    print(f"  exhaust from the work already happening, so the models stop going blind and the people move up")
    print(f"  to commanding a team of apprentices that absorbs the toil. Nobody is replaced. The work multiplies.")
    print(f"  {p.dim}What is real today: the signed capture, the provenance, the handback routing, the tamper-evidence.{p.end}")
    print(f"  {p.dim}What the pilot proves on real data: that the free signal trains a model as well as the paid labels.{p.end}")
    print(f"  {bar}")
    print()

    everything_held = (
        story_aligned and ok and (not bad_ok) and clean_ok
        and handbacks >= 1 and apprentice_actions == 0
    )
    if not everything_held:
        print(f"{p.red}  APPRENTICE DEMO FAIL{p.end} — a beat did not behave as scripted "
              f"(aligned={story_aligned}, verify={ok}, tamper_caught={not bad_ok}, clean={clean_ok}, "
              f"handbacks={handbacks}, apprentice_actions={apprentice_actions}).")
        return 1
    print(f"{p.green}  APPRENTICE DEMO OK{p.end} — watched the work, learned the easy class, handed the hard case back, proved the record.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="APPRENTICE narrative demo (an analyst works, an apprentice learns).")
    ap.add_argument("--plain", action="store_true", help="no ANSI colors (for runbook capture)")
    args = ap.parse_args()
    return play(plain=args.plain)


if __name__ == "__main__":
    sys.exit(main())
