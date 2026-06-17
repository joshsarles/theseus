# Contributing — Warhacker event repo

## License + IP boundary (read before first commit)
- Everything in THIS repo is intended **AGPL-3.0** (event default). Treat every line you add as public.
- **Retained IP rides only as pinned wheels/containers** brought to the event as pre-existing IP (Warhacker terms: vendors retain existing IP + enhancements). It is NEVER vendored, copied, or pasted here. The allowlist of what may live in this repo: schemas, the `referee/*` glue, CoT helpers, the reference chain, fixtures (synthetic), console, zarf/lula skeletons, docs.
- The **IP guard** (`scripts/ip_guard.py`) blocks commits that import retained modules or add files outside the allowlist. Install: `make hooks`. Do not bypass it; if it blocks something you think is fine, ask LEAD — never force.
- HARD GATE: nothing is pushed to any remote until LEAD confirms the legal scope check is cleared.

## Workflow (pickup-team discipline)
- `main` is the demo. It must pass `make smoke` at all times. Freeze: Day 3, 1000.
- Branch per task (`slot/short-name`), small PRs, LEAD or BE reviews; merge fast, revert faster.
- Every merge to `main`: `make smoke` locally first. If smoke breaks on `main`, fixing it preempts all other work.
- Demo fallbacks are code paths, not hopes: if your feature can fail on stage, it ships with its fallback flag.

## Style
- Python 3.10+, stdlib-only in this repo (production capability arrives via the wheels at the event).
- Complete types, small functions; stub bodies are fine (`raise NotImplementedError("Day 1: <task>")`) — broken types are not.
- No secrets, no API keys, no dataset files in git (fixtures are generated; large data stays on the SSD).
