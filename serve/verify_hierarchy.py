#!/usr/bin/env python3
"""THESEUS ship hierarchy — end-to-end verification (all real, no mocks).

Proves the offline ship hierarchy on ONE Mac, with NO Pi required and WITHOUT touching
the founder's live UI on :8501:

  edge node (machinery) ─ model_server.py + report_up.py ─┐
                                                          ├─► brain api.py (ephemeral port)
  edge node (contacts)  ─ model_server.py + report_up.py ─┘     aggregates → /api/state

Each step prints PASS/FAIL:
  1. brain comes up on an EPHEMERAL port (never :8501), isolated record + nodes dir
  2. two REAL edge servers come up (machinery=v4 sklearn, contacts=v3 sklearn), /health ok
  3. each node reports UP (report_up.py --once); brain ACKs + seals a node_report leaf
  4. brain /api/state shows BOTH systems live with their REAL model versions + health
  5. the brain's tamper-evident record verifies PASS (chain + merkle intact incl. node_reports)
  6. a node going stale (past TTL) falls back to standby — honest, no phantom green
  7. a node whose LOCAL edge server is down still reports health=down (degraded, not silent)

Self-contained:  python3 serve/verify_hierarchy.py
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEMO = ROOT / "demo"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DEMO))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _get(base: str, path: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode())


def _wait_up(base: str, path: str = "/health", tries: int = 60) -> bool:
    for _ in range(tries):
        try:
            _get(base, path, timeout=2)
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main() -> int:
    print("THESEUS · ship-hierarchy verification (real edge nodes → brain, offline)\n")

    work = Path(tempfile.mkdtemp(prefix="theseus_hier_"))
    brain_record = work / "brain_record"
    nodes_dir = work / "nodes"
    brain_record.mkdir(parents=True)
    nodes_dir.mkdir(parents=True)

    # Isolate the node registry so we NEVER write into the live brain's demo/out/nodes.
    os.environ["THESEUS_NODES_DIR"] = str(nodes_dir)

    # Each edge node gets its own record dir (its OWN tamper-evident record on the Pi).
    mach_record = work / "machinery_record"
    cont_record = work / "contacts_record"

    # Import AFTER setting THESEUS_NODES_DIR so the brain reads the isolated registry.
    import node_registry  # noqa: E402
    import api as brain_api  # noqa: E402
    from model_server import build_server  # noqa: E402
    import report_up  # noqa: E402
    from _record import seal as record_seal, verify as record_verify  # noqa: E402

    servers: list[ThreadingHTTPServer] = []
    threads: list[threading.Thread] = []

    def serve(httpd: ThreadingHTTPServer) -> None:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        servers.append(httpd)
        threads.append(t)

    try:
        # ── seed the brain's record with one genuine leaf so verify_dir has a chain ──
        record_seal(brain_record, "boot", "hierarchy-verify", {"note": "test brain boot"})

        # ── 1. brain on an EPHEMERAL port (NOT :8501) ──
        brain_port = _free_port()
        brain_api.Handler.record_dir = brain_record
        brain_httpd = ThreadingHTTPServer(("127.0.0.1", brain_port), brain_api.Handler)
        serve(brain_httpd)
        brain = f"http://127.0.0.1:{brain_port}"
        up = _wait_up(brain, "/api/health")
        assert brain_port != 8501, "refusing to bind :8501 (founder's live UI)"
        h = _get(brain, "/api/health") if up else {}
        check("1. brain up on ephemeral port (not :8501)", up and h.get("ok") is True,
              f"port={brain_port} record_verifies={h.get('record_verifies')}")

        # ── 2. two REAL edge servers ──
        # machinery -> the current promoted model; contacts -> the previous version if a
        # second promotion exists (distinct real versions), else current too. Either way
        # each node reports ITS server's REAL /health version — the point of the check.
        mach_port = _free_port()
        cont_port = _free_port()
        prev_dir = DEMO / "models" / "previous"
        cont_model_dir = prev_dir if (prev_dir / "meta.json").exists() else DEMO / "models" / "current"
        mach_httpd = build_server("127.0.0.1", mach_port, DEMO / "models" / "current", mach_record)
        cont_httpd = build_server("127.0.0.1", cont_port, cont_model_dir, cont_record)
        serve(mach_httpd)
        serve(cont_httpd)
        mach = f"http://127.0.0.1:{mach_port}"
        cont = f"http://127.0.0.1:{cont_port}"
        mach_up = _wait_up(mach)
        cont_up = _wait_up(cont)
        mh = _get(mach, "/health") if mach_up else {}
        ch = _get(cont, "/health") if cont_up else {}
        check("2. two real edge servers serving (machinery, contacts)",
              mach_up and cont_up and mh.get("status") == "ok" and ch.get("status") == "ok",
              f"machinery v{mh.get('model_version')} ({mh.get('framework')}), "
              f"contacts v{ch.get('model_version')} ({ch.get('framework')})")

        # ── 3. each node reports UP; brain ACKs + seals node_report ──
        ok_m, resp_m = report_up.report_once(brain, "pi1-machinery", "machinery", mach,
                                             mach_record, timeout=10)
        ok_c, resp_c = report_up.report_once(brain, "pi2-contacts", "contacts", cont,
                                             cont_record, timeout=10)
        check("3. both edge nodes reported UP + sealed at brain",
              ok_m and ok_c and resp_m.get("sealed") == "node_report"
              and resp_c.get("sealed") == "node_report",
              f"machinery leaf={str(resp_m.get('leaf_hash'))[:10]}…, "
              f"contacts leaf={str(resp_c.get('leaf_hash'))[:10]}…")

        # ── 4. brain /api/state shows BOTH systems live with REAL versions + health ──
        state = _get(brain, "/api/state")
        sysmap = {s["key"]: s for s in state["systems"]}
        m_sys = sysmap.get("machinery", {})
        c_sys = sysmap.get("contacts", {})
        m_node = m_sys.get("node", {})
        c_node = c_sys.get("node", {})
        live_ok = (
            m_sys.get("live") is True and c_sys.get("live") is True
            and m_node.get("model_version") == mh.get("model_version")
            and c_node.get("model_version") == ch.get("model_version")
            and m_node.get("node_id") == "pi1-machinery"
            and c_node.get("node_id") == "pi2-contacts"
            and m_node.get("health") == "ok" and c_node.get("health") == "ok"
            and state["nodes"]["live"] == 2
        )
        check("4. brain aggregates BOTH as live with real versions + health",
              live_ok,
              f"machinery=v{m_node.get('model_version')}/{m_node.get('health')}, "
              f"contacts=v{c_node.get('model_version')}/{c_node.get('health')}, "
              f"nodes.live={state['nodes']['live']}")

        # ── 5. brain record verifies PASS (chain + merkle, incl. the node_report leaves) ──
        vok, bad, msg = record_verify(brain_record)
        n_node_reports = state["record"]["events"].get("node_report", 0)
        check("5. brain tamper-evident record verifies PASS",
              vok and n_node_reports == 2,
              f"{msg} · node_report leaves={n_node_reports}")

        # ── 6. a node going stale -> system falls back to standby (honest) ──
        # Age the machinery node's report past TTL by rewriting received_unix in the
        # registry (simulates the Pi going dark / missing many beats). No new report.
        mach_file = nodes_dir / "pi1-machinery.json"
        rec = json.loads(mach_file.read_text())
        rec["received_unix"] = time.time() - (node_registry.TTL_SECONDS + 30)
        mach_file.write_text(json.dumps(rec))
        state2 = _get(brain, "/api/state")
        sysmap2 = {s["key"]: s for s in state2["systems"]}
        m_sys2 = sysmap2.get("machinery", {})
        c_sys2 = sysmap2.get("contacts", {})
        # machinery: stale node => no live node overlay. (CBM model still locally trained
        # in the live demo record, but THIS brain's isolated record has no model_promoted,
        # so machinery should be standby / not-live and carry no fresh node block.)
        stale_ok = (
            "node" not in m_sys2  # stale node dropped from the overlay
            and state2["nodes"]["live"] == 1   # only contacts still fresh
            and c_sys2.get("live") is True
        )
        check("6. stale node falls back to standby (TTL expiry, no phantom green)",
              stale_ok,
              f"machinery live={m_sys2.get('live')} has_node={'node' in m_sys2}, "
              f"contacts live={c_sys2.get('live')}, nodes.live={state2['nodes']['live']}")

        # ── 7. a node whose LOCAL edge server is down still reports health=down ──
        cont_httpd.shutdown()
        time.sleep(0.3)
        ok_d, resp_d = report_up.report_once(brain, "pi2-contacts", "contacts", cont,
                                            cont_record, timeout=5)
        state3 = _get(brain, "/api/state")
        c_sys3 = {s["key"]: s for s in state3["systems"]}.get("contacts", {})
        down_ok = (
            ok_d  # the report itself still reached the brain
            and resp_d.get("_sent_health") == "down"
            and c_sys3.get("node", {}).get("health") == "down"
            and c_sys3.get("severity") == "critical"  # down -> critical, not green
        )
        check("7. node with dead local server reports health=down (degraded, not silent)",
              down_ok,
              f"sent_health={resp_d.get('_sent_health')}, "
              f"brain shows contacts={c_sys3.get('node', {}).get('health')}/"
              f"{c_sys3.get('severity')}")

    finally:
        for s in servers:
            try:
                s.shutdown()
                s.server_close()
            except Exception:
                pass
        shutil.rmtree(work, ignore_errors=True)
        os.environ.pop("THESEUS_NODES_DIR", None)

    # ── summary ──
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"\n  {passed}/{total} checks passed")
    if passed == total:
        print(f"  [{PASS}] THESEUS ship hierarchy verified end-to-end (offline, no Pi, :8501 untouched)")
        return 0
    print(f"  [{FAIL}] hierarchy verification FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
