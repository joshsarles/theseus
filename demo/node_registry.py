"""THESEUS — edge-node report registry (the brain's view of its reporting edge nodes).

Each ship-system edge device (Raspberry Pi-class) POSTs UP a small report to the
brain (demo/api.py  POST /api/node-report). The brain persists the LAST report per
node as a tiny JSON file under demo/out/nodes/ — stdlib only, no DB, offline-safe.

build_state() reads this registry to make the CIC's `systems` reflect REAL edge
nodes: a system shows "live" with its actual model version + node health ONLY if a
node for that system is genuinely reporting AND its report is fresh. Reports older
than TTL_SECONDS are treated as STALE -> the system falls back to standby. Honest by
construction: no node reporting => not live.

This module is intentionally dependency-free and shared by api.py (read+write).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Default lives under demo/out/ (gitignored). Override with THESEUS_NODES_DIR so tests /
# multiple brain instances can isolate their node registry without touching the live one.
NODES_DIR = Path(os.environ.get("THESEUS_NODES_DIR", str(HERE / "out" / "nodes")))

# A node report older than this (seconds) is considered STALE -> system -> standby.
# Edge nodes report on an interval (default 15s in serve/report_up.py); 60s gives a
# few missed beats of slack before we stop trusting the picture.
TTL_SECONDS = 60

# Conservative node_id charset so a report can never write outside NODES_DIR.
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]")


def _safe_node_id(node_id: str) -> str:
    nid = _SAFE_ID.sub("_", str(node_id or "").strip())
    return nid[:128] or "unknown"


def _path_for(node_id: str) -> Path:
    # Two barriers against path traversal: (1) _safe_node_id strips every char outside
    # [A-Za-z0-9._-] (so '/' can never appear), and (2) resolve() + is_relative_to()
    # asserts the final path stays inside NODES_DIR — a containment check that rejects
    # any traversal attempt outright (and is recognized as a path-injection barrier).
    base = NODES_DIR.resolve()
    p = (base / f"{_safe_node_id(node_id)}.json").resolve()
    if not p.is_relative_to(base):
        raise ValueError(f"node report path escapes the registry: {node_id!r}")
    return p


def record_report(report: dict, *, now: float | None = None) -> dict:
    """Persist a node's report (last-write-wins per node_id). Returns the stored record.

    The stored record adds a server-side `received_unix` so staleness is judged by the
    brain's clock, not the (possibly skewed) edge clock — DDIL-honest.
    """
    now = time.time() if now is None else now
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    node_id = _safe_node_id(report.get("node_id"))
    stored = dict(report)
    stored["node_id"] = node_id
    stored["received_unix"] = now
    tmp = _path_for(node_id).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stored, sort_keys=True, indent=2))
    tmp.replace(_path_for(node_id))   # atomic on POSIX
    return stored


def _read_one(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_nodes(*, now: float | None = None, ttl: int = TTL_SECONDS) -> list[dict]:
    """All known node reports, each annotated with age_seconds + fresh (not stale)."""
    now = time.time() if now is None else now
    out: list[dict] = []
    if not NODES_DIR.exists():
        return out
    for p in sorted(NODES_DIR.glob("*.json")):
        rec = _read_one(p)
        if rec is None:
            continue
        recv = float(rec.get("received_unix", 0) or 0)
        age = max(0.0, now - recv)
        rec["age_seconds"] = round(age, 1)
        rec["fresh"] = age <= ttl
        out.append(rec)
    return out


def live_systems(*, now: float | None = None, ttl: int = TTL_SECONDS) -> dict[str, dict]:
    """Map system-key -> the freshest FRESH node report for that system.

    Only fresh (non-stale) reports count. If two nodes claim the same system, the most
    recently received fresh one wins (so a re-homed node supersedes a dead one).
    """
    now = time.time() if now is None else now
    best: dict[str, dict] = {}
    for rec in load_nodes(now=now, ttl=ttl):
        if not rec.get("fresh"):
            continue
        system = str(rec.get("system", "")).strip().lower()
        if not system:
            continue
        cur = best.get(system)
        if cur is None or float(rec.get("received_unix", 0)) > float(cur.get("received_unix", 0)):
            best[system] = rec
    return best
