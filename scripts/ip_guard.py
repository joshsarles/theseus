#!/usr/bin/env python3
"""Pre-commit IP guard: keeps retained IP out of the AGPL event repo.

Blocks staged changes that (a) import retained modules, (b) add files outside the
allowlist roots, or (c) look like vendored production code. Conservative on purpose:
a false block costs a question to LEAD; a false pass costs the company.
"""
from __future__ import annotations

import subprocess
import sys

ALLOWED_ROOTS = (
    "referee/", "cot/", "console/", "tests/", "fixtures/", "scripts/", "docs/",
    "zarf/", "lula/", "demo/", "deploy/", "ingest/", "eval/", "models/", "frontend/",
    "analytics/",  # team analytics container (Tommy/Juan)
    "train.py", "inspect_data.py", "docker-compose.yml", "requirements.txt",  # team root files (Nick/Juan)
    "Makefile", "README.md", "CONTRIBUTING.md",
    "KANBAN.md", "ROADMAP.md", "pyproject.toml", ".gitignore", "LICENSE",
)

# Retained-IP import roots (production capability arrives via wheels at the event;
# wheels are installed, never vendored or imported in repo source committed here).
FORBIDDEN_IMPORT_ROOTS = (
    # Bare root blocks ALL crucible.* imports (incl. crucible.comparison, which ships
    # in the retained wheel but was not previously listed — gap closed Jun 12).
    "crucible",
    "crucible.scoring", "crucible.ddil.orchestrator", "crucible.ddil.recipes",
    "crucible.drift_narrative_fingerprinting", "crucible.counterfactual_engine",
    "crucible.human.baselines", "crucible.sleeper_probe", "crucible.adversarial_replay",
    "force_core", "forceos", "starhelm",
)

FORBIDDEN_PATH_HINTS = ("src/crucible/", "force-core/", "Projects/Crucible", "Projects/Starhelm")


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def staged_blob(path: str) -> str:
    out = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def main() -> int:
    errors: list[str] = []
    for path in staged_files():
        if not path.startswith(ALLOWED_ROOTS):
            errors.append(f"PATH outside allowlist: {path}")
            continue
        if any(h in path for h in FORBIDDEN_PATH_HINTS):
            errors.append(f"retained-IP path hint in: {path}")
        if path.endswith((".py", ".rs", ".toml", ".yaml", ".yml", ".json", ".md")):
            blob = staged_blob(path)
            for root in FORBIDDEN_IMPORT_ROOTS:
                if f"import {root}" in blob or f"from {root}" in blob:
                    errors.append(f"retained-IP import '{root}' in: {path}")
    if errors:
        print("IP GUARD BLOCKED THIS COMMIT:")
        for e in errors:
            print(f"  ✗ {e}")
        print("If you believe this is wrong, ask LEAD. Never bypass with --no-verify.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
