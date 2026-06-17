"""Checks for the GUARDIAN narrative demo (the Cannonico case).

These guard the STORY layer only — they never touch the engine's own smoke contract.
Run from the repo root:  python3 -m pytest tests/ -q

Two things matter and are asserted here:
  1. The engine's verdict matches the author's intent on every step (story fidelity:
     what the narration says "out of bounds" is exactly what the gate HALTs on).
  2. The proof beat behaves: clean record verifies, a one-byte tamper is caught,
     a restored record verifies again. (Advisory-only; the gate, not the story, judges.)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from referee.chain import LocalHashChain, tamper, verify_dir  # noqa: E402
from referee.intake import ObservationIngestor  # noqa: E402
from referee.policy import evaluate_policy, load_policy  # noqa: E402

POLICY = ROOT / "fixtures" / "policy_cannonico.json"


def _scenario() -> object:
    spec = importlib.util.spec_from_file_location(
        "scenario_cannonico", ROOT / "fixtures" / "scenario_cannonico.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def steps() -> list:
    return _scenario().steps()  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def policy():
    return load_policy(POLICY)


def _judge_all(steps: list, policy) -> list[tuple]:
    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)
    out = []
    for s in steps:
        chained = ingestor.ingest(s.to_jsonl())
        decision = evaluate_policy(chained.obs, policy)
        out.append((s, decision))
    return out


def test_story_has_a_clean_start_and_clean_recovery(steps: list) -> None:
    # A general should see normal flying first, and a clean recovery last.
    assert steps[0].expect == "in"
    assert steps[-1].expect == "in"


def test_story_has_at_least_three_clear_drifts(steps: list) -> None:
    out_of_bounds = [s for s in steps if s.expect == "out"]
    assert len(out_of_bounds) >= 3, "the agent must visibly drift out of bounds in 2-3+ clear ways"


def test_strike_escalation_is_in_the_story(steps: list) -> None:
    # The headline beat: the AI escalates to an action reserved for a human.
    strike = [s for s in steps if s.obs.get("decision_type") == "strike_recommendation"]
    assert strike, "the story must include the agent escalating to a forbidden action (strike)"
    assert all(s.expect == "out" for s in strike)


def test_engine_verdict_matches_author_intent_on_every_step(steps: list, policy) -> None:
    # Story fidelity: the GATE, not the narration, decides. They must agree on every step,
    # so the runbook can never claim "out of bounds" on a step the engine passes.
    mismatches = []
    for s, decision in _judge_all(steps, policy):
        engine_out = decision.gate != "PASS"
        author_out = s.expect == "out"
        if engine_out != author_out:
            rules = ",".join(v.rule for v in decision.violations) or "-"
            mismatches.append(f"step {s.step}: author={s.expect} engine_gate={decision.gate} ({rules})")
    assert not mismatches, "engine and narration disagree:\n" + "\n".join(mismatches)


def test_the_three_named_drifts_are_caught_by_the_engine(steps: list, policy) -> None:
    # The geofence walk-out, the low-confidence read, and the strike escalation must each
    # be HALTed by the engine with the rule a general would expect.
    rules_by_step = {
        s.step: {v.rule for v in d.violations} for s, d in _judge_all(steps, policy)
    }
    # geofence walk-out
    assert any("geofence" in rs for rs in rules_by_step.values())
    # acting on a low-confidence read
    assert any("confidence_floor" in rs for rs in rules_by_step.values())
    # acting on a stale read
    assert any("stale_decision" in rs for rs in rules_by_step.values())
    # forbidden protected-class context
    assert any("forbidden_class_adjacency" in rs for rs in rules_by_step.values())
    # escalation to an action reserved for a human
    assert any("forbidden_decision_type" in rs for rs in rules_by_step.values())


def test_proof_beat_clean_then_tamper_caught_then_clean_again(tmp_path: Path, steps: list, policy) -> None:
    import json

    chain = LocalHashChain()
    ingestor = ObservationIngestor(chain)
    for s in steps:
        chained = ingestor.ingest(s.to_jsonl())
        decision = evaluate_policy(chained.obs, policy)
        for v in decision.violations:
            chain.append("violation", v.obs_id, json.dumps(v.__dict__).encode())

    out = tmp_path / "out_guardian"
    chain.write(out)

    ok, _, _ = verify_dir(out)
    assert ok, "freshly written record must verify"

    target = min(8, len(chain.leaves) - 1)
    tamper(out, target)
    bad_ok, first_bad, _ = verify_dir(out)
    assert not bad_ok, "a one-byte change must be caught"
    assert first_bad == target, "GUARDIAN must point at the exact altered entry"

    chain.write(out)
    clean_ok, _, _ = verify_dir(out)
    assert clean_ok, "restored true record must verify again"


def test_demo_runner_returns_ok() -> None:
    # End-to-end: the runner's own self-check must pass (caught drift + human + proof).
    import referee.guardian_demo as gd

    assert gd.play(plain=True) == 0
