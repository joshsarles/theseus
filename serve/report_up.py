#!/usr/bin/env python3
"""THESEUS edge→brain reporting — the ship hierarchy beat (edge node reports UP).

Each ship-system edge node (Raspberry Pi-class) runs THIS alongside its local model
server (serve/model_server.py). On an interval it builds a small report from its OWN
local state and POSTs it UP to the ship brain (demo/api.py  POST /api/node-report):

    {node_id, system, model, model_version, framework, health, last_good,
     leaf_hashes[], edge_unix, reload_count}

Where the fields come from (all LOCAL — no shore/brain dependency to produce a report):
  * model_version / framework / health / reload_count  <- GET <local edge>/health + /version
  * last_good                                          <- last edge_model_loaded version we saw
  * leaf_hashes[]                                      <- last N sealed leaf hashes from the
                                                          edge's OWN tamper-evident record dir
                                                          (provenance the brain can cross-check)

DDIL-resilient by construction:
  * The edge keeps SERVING locally regardless of whether the brain is reachable. This
    process only REPORTS; it never gates inference.
  * Brain unreachable / slow / 5xx -> log, keep last-good report, retry next tick. The
    edge does not crash and does not stop. Exponential-ish backoff is bounded.
  * Offline over LAN / Tailscale: just point --brain at the brain's LAN/Tailscale URL.

Run on the Pi (alongside model_server.py):
    python3 serve/report_up.py \
        --brain http://<brain-host>:8077 \
        --edge  http://127.0.0.1:8080 \
        --node-id pi1-machinery --system machinery \
        --record-dir demo/out/record --interval 15

One-shot (report once and exit, e.g. for the systemd ExecStartPost smoke):
    python3 serve/report_up.py ... --once
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_RECORD_DIR = ROOT / "demo" / "out" / "record"


def _get_json(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": "non-json error body"}


def recent_leaf_hashes(record_dir: Path, n: int = 5) -> list[str]:
    """Last N sealed leaf hashes from the edge's OWN record (newest last).

    Pure stdlib, tail-light: we read the file but only keep the trailing hashes. If the
    record is missing (fresh node, never sealed anything) we return [] — honest.
    """
    cp = Path(record_dir) / "chain.jsonl"
    if not cp.exists():
        return []
    hashes: list[str] = []
    try:
        for line in cp.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                hashes.append(json.loads(line)["leaf_hash"])
            except Exception:
                continue
    except Exception:
        return []
    return hashes[-n:]


def last_good_version(record_dir: Path) -> int | None:
    """The newest version we successfully hot-swapped to, from edge_model_loaded leaves."""
    cp = Path(record_dir) / "chain.jsonl"
    if not cp.exists():
        return None
    import base64
    last = None
    try:
        for line in cp.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "edge_model_loaded":
                try:
                    d = json.loads(base64.b64decode(row["record_b64"]))
                    last = d.get("version", last)
                except Exception:
                    pass
    except Exception:
        return None
    return last


def build_report(node_id: str, system: str, edge: str, record_dir: Path,
                 timeout: float) -> dict:
    """Assemble one report from purely-local sources. Always returns a report; if the
    LOCAL edge server is unreachable we still report (health=down) so the brain shows
    the node as degraded rather than the node going silent."""
    report: dict = {
        "node_id": node_id,
        "system": system,
        "edge_unix": time.time(),
        "leaf_hashes": recent_leaf_hashes(record_dir),
        "last_good": last_good_version(record_dir),
    }
    try:
        health = _get_json(f"{edge.rstrip('/')}/health", timeout)
        report["model_version"] = health.get("model_version")
        report["framework"] = health.get("framework")
        report["reload_count"] = health.get("reload_count")
        report["health"] = "ok" if str(health.get("status")) == "ok" else "degraded"
        # model name: the edge server doesn't return it on /health; default by system.
        report["model"] = os.environ.get("EDGE_MODEL_NAME") or _default_model(system)
    except Exception as e:
        # The LOCAL edge server is down/unreachable. Still report UP so the brain knows
        # the node is degraded (honest) instead of the node disappearing.
        report["health"] = "down"
        report["model"] = os.environ.get("EDGE_MODEL_NAME") or _default_model(system)
        report["edge_error"] = str(e)[:120]
    return report


def _default_model(system: str) -> str:
    return {"machinery": "theseus-cbm", "contacts": "theseus-ae"}.get(
        system, f"theseus-{system}")


def report_once(brain: str, node_id: str, system: str, edge: str,
                record_dir: Path, timeout: float) -> tuple[bool, dict]:
    report = build_report(node_id, system, edge, record_dir, timeout)
    try:
        code, resp = _post_json(f"{brain.rstrip('/')}/api/node-report", report, timeout)
    except Exception as e:
        return False, {"error": f"brain unreachable: {str(e)[:120]}", "report": report}
    ok = 200 <= code < 300 and resp.get("ok")
    resp["_sent_health"] = report.get("health")
    resp["_sent_version"] = report.get("model_version")
    return bool(ok), resp


def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS edge→brain reporting (the hierarchy beat).")
    ap.add_argument("--brain", default=os.environ.get("BRAIN_URL", "http://127.0.0.1:8077"),
                    help="ship brain base URL (LAN / Tailscale; default :8077)")
    ap.add_argument("--edge", default=os.environ.get("EDGE_URL", "http://127.0.0.1:8080"),
                    help="this node's LOCAL edge server base URL")
    ap.add_argument("--node-id", default=os.environ.get("NODE_ID", "edge-node"),
                    help="unique node id, e.g. pi1-machinery")
    ap.add_argument("--system", default=os.environ.get("NODE_SYSTEM", "machinery"),
                    help="ship system this node serves, e.g. machinery | contacts")
    ap.add_argument("--record-dir", default=os.environ.get("RECORD_DIR", str(DEFAULT_RECORD_DIR)),
                    help="this node's OWN record dir (for provenance leaf hashes)")
    ap.add_argument("--interval", type=float, default=float(os.environ.get("REPORT_INTERVAL", "15")),
                    help="seconds between reports")
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("REPORT_TIMEOUT", "10")))
    ap.add_argument("--once", action="store_true", help="report once and exit")
    a = ap.parse_args()

    record_dir = Path(a.record_dir)
    print(f"THESEUS report_up · node={a.node_id} system={a.system}")
    print(f"  edge (local) : {a.edge}")
    print(f"  brain (up)   : {a.brain}/api/node-report   interval={a.interval}s")

    if a.once:
        ok, resp = report_once(a.brain, a.node_id, a.system, a.edge, record_dir, a.timeout)
        print(("  [up] OK   " if ok else "  [up] FAIL ") + json.dumps(resp))
        return 0 if ok else 1

    backoff = a.interval
    fails = 0
    while True:
        ok, resp = report_once(a.brain, a.node_id, a.system, a.edge, record_dir, a.timeout)
        if ok:
            fails = 0
            backoff = a.interval
            print(f"  [up] reported (health={resp.get('_sent_health')} "
                  f"v={resp.get('_sent_version')} sealed={resp.get('sealed')})")
            sleep = a.interval
        else:
            fails += 1
            # Bounded backoff so a long brain outage doesn't hammer the link, but we keep
            # trying forever — the edge never gives up reporting UP.
            backoff = min(backoff * 1.5, max(a.interval * 8, 120))
            print(f"  [up] brain unreachable (fail #{fails}); retry in {backoff:.0f}s "
                  f"— {resp.get('error')}", file=sys.stderr)
            sleep = backoff
        try:
            time.sleep(sleep)
        except KeyboardInterrupt:
            print("\n  report_up stopped")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
