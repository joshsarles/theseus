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


_POS_CACHE: dict = {}


def _positions(mmsis: set) -> dict:
    """Last known (lat,lon) for the flagged MMSIs, from the real AIS CSV. Cached once."""
    global _POS_CACHE
    if not _POS_CACHE:
        csv_path = HERE.parent / "data" / "datasets" / "marinecadastre_us" / "AIS_2024_01_01.csv"
        if csv_path.exists():
            import csv as _csv
            with csv_path.open() as f:
                r = _csv.reader(f)
                next(r, None)
                for i, row in enumerate(r):
                    if i > 1_500_000:
                        break
                    try:
                        _POS_CACHE[row[0]] = (round(float(row[2]), 5), round(float(row[3]), 5))
                    except (IndexError, ValueError):
                        pass
        else:
            _POS_CACHE["__none__"] = (0, 0)  # mark "tried" so we don't rescan every request
    return {m: _POS_CACHE[m] for m in mmsis if m in _POS_CACHE}


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

    ais = by_kind.get("ais_anomaly", [])
    pos = _positions({lf["data"].get("mmsi") for lf in ais})
    contacts = []
    for lf in ais:
        d = lf["data"]
        ll = pos.get(d.get("mmsi"))
        contacts.append({
            "id": lf.get("obs_id"),
            "mmsi": d.get("mmsi"),
            "type": d.get("type"),
            "vessel_class": d.get("vessel_class"),
            "confidence": d.get("confidence"),
            "why": d.get("why"),
            "recommended_action": d.get("recommended_action"),
            "lat": ll[0] if ll else None,
            "lon": ll[1] if ll else None,
            "status": "pending",   # awaiting watchstander ACCEPT/OVERRIDE
        })

    ok, bad, msg = verify_dir(record_dir) if (record_dir / "chain.jsonl").exists() else (False, None, "no record")

    # The ship's organs — the subsystems THESEUS monitors. HONEST: a system is "live" only
    # where a model is actually deployed; the rest are instrumented organs (framework), shown
    # on standby — never claimed green. This is the "one ship, all systems" picture.
    has_ae = any(lf["data"].get("kind") == "autoencoder-anomaly" for lf in by_kind.get("model_trained", []))
    crit = sum(1 for c in contacts if c["type"] == "position_jump")
    systems = [
        {"key": "propulsion", "label": "PROPULSION / ENGINEERING", "live": bool(machinery),
         "severity": "nominal" if machinery else "standby",
         "detail": (f"gas-turbine decay model v{machinery['version']} · RMSE {machinery['rmse']}" if machinery else "model pending")},
        {"key": "machinery", "label": "MACHINERY / HM&E", "live": bool(machinery) or has_ae,
         "severity": "nominal" if (machinery or has_ae) else "standby",
         "detail": "condition-based maintenance" + (" + autoencoder PdM" if has_ae else "")},
        {"key": "contacts", "label": "CONTACTS / TACTICAL", "live": True,
         "severity": ("critical" if crit else ("warning" if contacts else "nominal")),
         "detail": f"{len(contacts)} track(s) flagged · {crit} possible spoof/jump"},
        {"key": "power", "label": "POWER & ELECTRICAL", "live": False, "severity": "standby", "detail": "organ instrumented · model pending"},
        {"key": "navigation", "label": "NAVIGATION", "live": False, "severity": "standby", "detail": "organ instrumented · model pending"},
        {"key": "damage_control", "label": "DAMAGE CONTROL", "live": False, "severity": "standby", "detail": "organ instrumented · model pending"},
        {"key": "readiness", "label": "READINESS", "live": False, "severity": "standby", "detail": "mission-capability rollup pending"},
    ]
    return {
        "ship": "THESEUS",
        "posture": "decision-support · human-in-command · SWAN-side",
        "systems": systems,
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

    def _send_html(self):
        page = Path(__file__).resolve().parent.parent / "frontend" / "cic.html"
        if not page.exists():
            self._send({"error": "frontend/cic.html missing"}, 404)
            return
        body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path in ("", "/index", "/cic"):     # the dashboard
            self._send_html()
            return
        try:
            state = build_state(self.record_dir)
        except Exception as e:
            self._send({"error": str(e)}, 500)
            return
        if path in ("/api/state", "/api"):
            self._send(state)
        elif path == "/api/contacts":
            self._send({"contacts": state["contacts"], "pending": state["human_in_command"]["pending"]})
        elif path == "/api/health":
            self._send({"ok": True, "record_verifies": state["record"]["verify_ok"], "leaves": state["record"]["leaf_count"]})
        else:
            self._send({"error": "not found", "routes": ["/", "/api/state", "/api/contacts", "/api/health"]}, 404)

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
