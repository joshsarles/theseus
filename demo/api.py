#!/usr/bin/env python3
"""THESEUS — ship-state JSON API (the frontend data contract).

Serves the watchstander board as JSON so the frontend (Gerardo/Aaron) can render it,
straight from the tamper-evident record. Read-only, stdlib only, CORS-enabled for a
dev frontend. The UI is the frontend lane; THIS is the data backend it fetches.

  python3 demo/api.py            # http://localhost:8077
  GET /api/state                 # full board: machinery + contacts + record integrity
  GET /api/contacts              # just the flagged contacts (recommendation cards)
  GET /api/health                # liveness + record verify status

Run the loop + ais_pol first (or point --record at any sealed record dir).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from referee.chain import verify_dir  # noqa: E402

RECORD = HERE / "out" / "record"


def _leaves(record_dir: Path) -> list[dict]:
    cp = record_dir / "chain.jsonl"
    out = []
    if cp.exists():
        for line in cp.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                row["data"] = json.loads(base64.b64decode(row["record_b64"]))
            except Exception:
                row["data"] = {}
            out.append(row)
    return out


def build_state(record_dir: Path) -> dict:
    """The frontend contract. Stable shape — keep keys stable as the UI builds on it."""
    leaves = _leaves(record_dir)
    by_kind: dict[str, list[dict]] = {}
    for lf in leaves:
        by_kind.setdefault(lf["kind"], []).append(lf)

    promo = by_kind.get("model_promoted", [])
    machinery = None
    if promo:
        d = promo[-1]["data"]
        machinery = {
            "model": "theseus-cbm",
            "version": d.get("version"),
            "rmse": d.get("rmse"),
            "framework": d.get("framework"),
            "status": "nominal",
            "promotions": len(promo),
        }

    contacts = []
    for lf in by_kind.get("ais_anomaly", []):
        d = lf["data"]
        contacts.append({
            "id": lf.get("obs_id"),
            "mmsi": d.get("mmsi"),
            "type": d.get("type"),
            "vessel_class": d.get("vessel_class"),
            "confidence": d.get("confidence"),
            "why": d.get("why"),
            "recommended_action": d.get("recommended_action"),
            "status": "pending",   # awaiting watchstander ACCEPT/OVERRIDE
        })

    ok, bad, msg = verify_dir(record_dir) if (record_dir / "chain.jsonl").exists() else (False, None, "no record")
    return {
        "ship": "THESEUS",
        "posture": "decision-support · human-in-command · SWAN-side",
        "machinery": machinery,
        "contacts": contacts,
        "human_in_command": {
            "pending": len(contacts),
            "note": "Theseus recommends; the watch officer decides. Nothing is actioned automatically.",
        },
        "record": {
            "verify_ok": ok,
            "first_bad_leaf": bad,
            "message": msg,
            "leaf_count": len(leaves),
            "events": {k: len(v) for k, v in sorted(by_kind.items())},
        },
    }


class Handler(BaseHTTPRequestHandler):
    record_dir = RECORD

    def _send(self, obj, code=200):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")   # dev frontend
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        try:
            state = build_state(self.record_dir)
        except Exception as e:
            self._send({"error": str(e)}, 500)
            return
        if self.path.rstrip("/") in ("/api/state", "/api", ""):
            self._send(state)
        elif self.path.rstrip("/") == "/api/contacts":
            self._send({"contacts": state["contacts"], "pending": state["human_in_command"]["pending"]})
        elif self.path.rstrip("/") == "/api/health":
            self._send({"ok": True, "record_verifies": state["record"]["verify_ok"], "leaves": state["record"]["leaf_count"]})
        elif self.path in ("/", "/index"):
            self._send({"service": "theseus-state-api", "routes": ["/api/state", "/api/contacts", "/api/health"]})
        else:
            self._send({"error": "not found", "routes": ["/api/state", "/api/contacts", "/api/health"]}, 404)

    def log_message(self, *a):  # quiet
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--record", default=str(RECORD))
    a = ap.parse_args()
    Handler.record_dir = Path(a.record)
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    print(f"THESEUS state API → http://localhost:{a.port}/api/state  (record: {a.record})")
    print("  routes: /api/state · /api/contacts · /api/health   (CORS *, read-only)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
