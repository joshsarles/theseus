"""Checks for the APPRENTICE narrative demo (an analyst works, an apprentice learns).

These guard the STORY layer only — they never touch the engine's own smoke contract.
Run from the repo root:  python3 -m pytest tests/ -q

What matters and is asserted here:
  1. Story fidelity: the engine's gate verdict matches the author's intent on every
     step (what the narration calls a "hard case / handback" is exactly what the gate
     flags; what it calls a clean "learnable" lesson is exactly what the gate passes).
  2. The apprentice never acts: every hard case is handed back, and there is at least
     one handback in the story.
  3. The proof beat behaves: clean record verifies, a one-byte tamper is caught, a
     restored record verifies again.
  4. The demo entrypoint returns success.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from referee.chain import LocalHashChain, tamper, verify_dir  # noqa: E402
from referee.intake import ObservationIngestor  # noqa: E402
from referee.policy import evaluate_policy, load_policy  # noqa: E402

POLICY = ROOT / "fixtures" / "policy_cannonico.json"


def _scenario() -> object:
    spec = importlib.util.spec_from_file_location(
        "scenario_apprentice", ROOT / "fixtures" / "scenario_apprentice.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_story_fidelity_gate_matches_intent() -> None:
    """Every step's authored intent (learnable vs handback) matches the engine's gate."""
    scenario = _scenario()
    policy = load_policy(POLICY)
    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)

    handbacks = 0
    learnable = 0
    for s in scenario.steps():  # type: ignore[attr-defined]
        chained = ingestor.ingest(s.to_jsonl())
        decision = evaluate_policy(chained.obs, policy)
        is_hard = decision.gate != "PASS"
        if s.expect == "handback":
            assert is_hard, f"step {s.step} authored handback but gate PASSed"
            handbacks += 1
        elif s.expect == "learnable":
            assert not is_hard, f"step {s.step} authored learnable but gate flagged {[v.rule for v in decision.violations]}"
            learnable += 1
        else:  # pragma: no cover - guards a typo in the scenario
            raise AssertionError(f"step {s.step} has unknown expect={s.expect!r}")

    assert handbacks >= 1, "the story must hand at least one hard case back to the human"
    assert learnable >= 1, "the story must capture at least one clean lesson"


def test_apprentice_never_acts() -> None:
    """No step delegates an action to the apprentice; the human confirms or decides every call."""
    scenario = _scenario()
    for s in scenario.steps():  # type: ignore[attr-defined]
        # roles are limited to: watch / suggest / draft / handback — none is "act"
        assert s.role in {"watch", "suggest", "draft", "handback"}, f"step {s.step} role={s.role!r}"
        # every handback is routed to the human
        if s.expect == "handback":
            assert s.role == "handback", f"step {s.step} is a hard case but role={s.role!r}"


def test_proof_beat_tamper_evident() -> None:
    """Clean record verifies; a one-byte tamper is caught; a restored record verifies again."""
    scenario = _scenario()
    policy = load_policy(POLICY)
    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)
    out = ROOT / "out_apprentice_test"

    for s in scenario.steps():  # type: ignore[attr-defined]
        chained = ingestor.ingest(s.to_jsonl())
        evaluate_policy(chained.obs, policy)
    chain.write(out)

    ok, _, _ = verify_dir(out)
    assert ok, "clean record should verify"

    tamper(out, min(8, len(chain.leaves) - 1))
    bad_ok, _, _ = verify_dir(out)
    assert not bad_ok, "tamper must be caught"

    chain.write(out)
    clean_ok, _, _ = verify_dir(out)
    assert clean_ok, "restored record should verify again"


def test_demo_entrypoint_ok() -> None:
    """The narrated demo returns success (exit 0) end to end."""
    from referee.apprentice_demo import play

    assert play(plain=True) == 0
