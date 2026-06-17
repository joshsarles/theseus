"""Regression guard for the THESEUS model-delivery loop (demo/).

Runs Stage -> Retrain -> Update on the committed real UCI #316 data and asserts:
the record verifies PASS, a model is promoted, and a second cycle bumps the version
and leaves a rollback copy. Pure subprocess + the record verifier — no extra deps
(sklearn used if present, else the stdlib OLS path; either way the loop must be green).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
RECORD = DEMO / "out" / "record"
sys.path.insert(0, str(ROOT))
from referee.chain import verify_dir  # noqa: E402


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DEMO / script)],
        cwd=str(ROOT), capture_output=True, text=True,
    )


def _clean() -> None:
    for d in ("out", "registry", "models"):
        shutil.rmtree(DEMO / d, ignore_errors=True)


def _version() -> int:
    import json
    return json.loads((DEMO / "models" / "current" / "meta.json").read_text())["version"]


def test_demo_loop_green_and_record_verifies():
    _clean()
    try:
        for step in ("stage_data.py", "retrain.py", "update_model.py"):
            r = _run(step)
            assert r.returncode == 0, f"{step} failed:\n{r.stdout}\n{r.stderr}"

        # the record verifies offline
        ok, bad, msg = verify_dir(RECORD)
        assert ok, f"record did not verify: {msg} (bad leaf {bad})"

        # a model was promoted to the live local slot, with a real metric
        import json
        meta = json.loads((DEMO / "models" / "current" / "meta.json").read_text())
        assert meta["version"] == 1
        assert 0.0 <= meta["rmse"] < 0.1, f"implausible RMSE {meta['rmse']}"
        assert (DEMO / "models" / "current" / "model.bin").exists()

        # second cycle: version bumps, rollback copy kept, record still verifies
        assert _run("retrain.py").returncode == 0
        assert _run("update_model.py").returncode == 0
        assert _version() == 2
        assert (DEMO / "models" / "previous" / "meta.json").exists(), "no rollback copy kept"
        ok2, _, msg2 = verify_dir(RECORD)
        assert ok2, f"record broke after 2nd cycle: {msg2}"
    finally:
        _clean()


def test_record_tamper_is_detected():
    """The moat: flipping one byte must SNAP the chain (tamper-evident)."""
    from referee.chain import tamper
    _clean()
    try:
        for step in ("stage_data.py", "retrain.py", "update_model.py"):
            assert _run(step).returncode == 0
        assert verify_dir(RECORD)[0] is True
        tamper(RECORD, 0)  # flip leaf 0
        ok, bad, _ = verify_dir(RECORD)
        assert ok is False and bad == 0, "tamper not detected — record is not tamper-evident"
    finally:
        _clean()
