#!/usr/bin/env python3
"""THESEUS edge serving — end-to-end verification (all real, no mocks).

Runs the whole shore→ship live-update story against a REAL running edge server and
prints PASS/FAIL for each checkpoint:

  1. server starts on the current model; GET /health is healthy + reports version/framework
  2. POST /predict returns a real CBM decay-coefficient prediction in plausible range
  3. shore promotes a new version (real demo loop) and delivers it; /version flips up
  4. the hot-swap was SEALED into the tamper-evident record (edge_model_loaded leaf)
  5. offline verify_dir on the record returns PASS (chain + merkle intact)
  6. a deliberately-broken delivery is REJECTED; the edge keeps serving last-good, no crash

Reproduce manually:
  python3 serve/model_server.py            # terminal A (leave running)
  python3 serve/verify_serve.py            # terminal B  (or just run this; it self-hosts)

This script self-hosts the server in a background thread on an ephemeral port, so it
is fully self-contained: `python3 serve/verify_serve.py`.
"""
from __future__ import annotations

import csv
import json
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEMO = ROOT / "demo"
CURRENT = DEMO / "models" / "current"
RECORD = DEMO / "out" / "record"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DEMO))

import deliver as deliver_mod  # noqa: E402
from model_server import build_server  # noqa: E402
from _record import verify as record_verify  # noqa: E402  (demo/_record.py)

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


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as r:
        return json.loads(r.read().decode())


def _post(base: str, path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{base}{path}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _wait_up(base: str, tries: int = 50) -> bool:
    for _ in range(tries):
        try:
            _get(base, "/health")
            return True
        except Exception:
            time.sleep(0.1)
    return False


def _sample_features() -> dict:
    """A real feature row from the staged CBM data, keyed by the server's feature list."""
    meta = json.loads((CURRENT / "meta.json").read_text())
    rows = list(csv.DictReader((DEMO / "data" / "staged.csv").open()))
    row = rows[len(rows) // 2]
    return {f: float(row[f]) for f in meta["features"]}


def main() -> int:
    print("THESEUS edge serving — end-to-end verification (real server, real loop)\n")

    # Ensure there is a current model to serve (run the loop once if needed).
    if not (CURRENT / "meta.json").exists():
        print("  (no current model — running demo loop once to seed it)")
        deliver_mod.run_loop()

    # ---- start a REAL edge server in-process on an ephemeral port ----
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    httpd = build_server("127.0.0.1", port, CURRENT, RECORD)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        up = _wait_up(base)
        check("1a. edge server starts (CPU-only)", up, base)
        if not up:
            return 1

        health = _get(base, "/health")
        check("1b. /health healthy + reports version/framework",
              health.get("status") == "ok" and "model_version" in health
              and health.get("gpu") is False,
              f"v{health.get('model_version')} {health.get('framework')} gpu={health.get('gpu')}")
        v_before = health["model_version"]

        # ---- /predict ----
        feats = _sample_features()
        status, pred = _post(base, "/predict", {"features": feats})
        p = pred.get("prediction")
        ok_pred = (status == 200 and isinstance(p, (int, float))
                   and 0.90 <= p <= 1.05)  # CBM decay coeff plausible band
        check("2. /predict returns a real CBM prediction", ok_pred,
              f"prediction={p} (target={pred.get('target')})")

        # ---- shore promotes v(N+1) and delivers it ----
        print("\n  -- shore→ship: promote a new version + deliver --")
        rc = deliver_mod.run_loop()
        check("3a. shore loop promotes a new version", rc == 0)
        res = deliver_mod.deliver(base, "http", CURRENT)
        v_after = res["after"]["version"]
        check("3b. /version flips up after delivery", v_after > v_before,
              f"v{v_before} -> v{v_after}")
        check("3c. hot-swap reported swapped + sealed",
              res["result"].get("swapped") and res["result"].get("sealed"),
              f"leaf={str(res['result'].get('leaf_hash'))[:12]}…")

        # ---- the swap is in the record ----
        chain = [json.loads(l) for l in (RECORD / "chain.jsonl").read_text().splitlines() if l.strip()]
        sealed_swap = any(r["kind"] == "edge_model_loaded" for r in chain)
        check("4. swap sealed as edge_model_loaded leaf", sealed_swap,
              f"{sum(r['kind']=='edge_model_loaded' for r in chain)} edge_model_loaded leaf(s)")

        # ---- offline verify of the whole record ----
        ok_v, bad, msg = record_verify(RECORD)
        check("5. verify_dir(record) returns PASS", ok_v, msg)

        # ---- DDIL: a deliberately-broken delivery is rejected, last-good kept ----
        print("\n  -- DDIL: deliver a BROKEN model, edge must keep last-good --")
        good_version = _get(base, "/version")["version"]
        bad_dir = ROOT / "serve" / "edge_inbox_bad"
        if bad_dir.exists():
            shutil.rmtree(bad_dir)
        bad_dir.mkdir(parents=True)
        # valid-looking meta, but model.bin bytes don't match the sealed sha256
        meta = json.loads((CURRENT / "meta.json").read_text())
        (bad_dir / "meta.json").write_text(json.dumps(meta))
        (bad_dir / "model.bin").write_bytes(b"\x00\x01CORRUPT-NOT-A-MODEL\x02\x03")
        status, rj = _post(base, "/reload", {"model_dir": str(bad_dir)})
        check("6a. broken delivery rejected (422)", status == 422 and rj.get("rejected"),
              rj.get("reason", "")[:70])
        still = _get(base, "/version")["version"]
        check("6b. edge still serving last-good after bad delivery", still == good_version,
              f"still v{still}")
        # server still alive + predicts?
        status2, pred2 = _post(base, "/predict", {"features": feats})
        check("6c. edge still serves /predict after bad delivery (no crash)",
              status2 == 200 and isinstance(pred2.get("prediction"), (int, float)),
              f"prediction={pred2.get('prediction')}")

    finally:
        httpd.shutdown()
        httpd.server_close()

    # ---- summary ----
    print("\n" + "=" * 64)
    n_pass = sum(1 for _, ok, _ in _results if ok)
    n = len(_results)
    print(f"  RESULT: {n_pass}/{n} checks PASS")
    for name, ok, _ in _results:
        print(f"    {PASS if ok else FAIL}  {name}")
    print("=" * 64)
    return 0 if n_pass == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
