#!/usr/bin/env python3
"""THESEUS edge inference server — the model deployed AT the edge (Raspberry Pi 5, 4GB).

Pi-realistic by construction:
  * CPU-only, NO GPU, NO CUDA.
  * stdlib http.server (zero web-framework deps; tiny RAM footprint).
  * Loads demo/models/current/ once, holds ONE model in memory at a time.

Endpoints
  GET  /health   -> {"status","model_version","framework","target","n_features","model_dir"}
  GET  /version  -> {"version","framework","target","model_sha256","features"}
  POST /predict  -> body {"features": {<name>: <value>, ...}}  (or {"inputs":[{...},...]} for a batch)
                    -> {"prediction": <float>, "model_version": N, "target": "..."}
  POST /reload   -> body {"model_dir": "<path>"}  (or none = re-read the configured dir)
                    Hot-swaps the live model. On success seals an `edge_model_loaded`
                    leaf into the tamper-evident record and flips /version.
                    On ANY load error it REJECTS the swap and keeps serving last-good
                    (DDIL-safe), returning 422 with the reason. The shore→ship
                    delivery tool (serve/deliver.py) drives this endpoint.

This is THESEUS objectives #3 (deploy/live-update at the edge) and #4 (stage from
shore, hot-swap, prove the swap) made real — no sneakernet, every swap sealed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Repo root on path so we can reuse the demo's record sealing (demo/_record.py)
# WITHOUT modifying any demo internals.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "demo"))   # for `_record`
sys.path.insert(0, str(HERE))            # for `model_core`

from model_core import LoadedModel, ModelLoadError, load_model  # noqa: E402
from _record import seal as record_seal  # noqa: E402  (demo/_record.py)

DEFAULT_MODEL_DIR = ROOT / "demo" / "models" / "current"
DEFAULT_RECORD_DIR = ROOT / "demo" / "out" / "record"


class ModelHolder:
    """Holds the single live model + serves the DDIL-safe hot-swap.

    Thread-safe: /predict reads under a lock; /reload swaps under the same lock so a
    request never sees a half-loaded model. The new model is fully built+validated
    OFF to the side first; the live pointer is only moved if that succeeds, so a bad
    delivery never displaces last-good.
    """

    def __init__(self, model_dir: Path, record_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.record_dir = Path(record_dir)
        self._lock = threading.Lock()
        self._model: LoadedModel = load_model(self.model_dir)  # fail-fast at startup
        self.loaded_unix = time.time()
        self.reload_count = 0
        self.last_rejected: dict | None = None

    @property
    def model(self) -> LoadedModel:
        return self._model

    def predict(self, feature_map: dict) -> float:
        with self._lock:
            return self._model.predict(feature_map)

    def reload(self, new_dir: Path | None) -> dict:
        """Attempt a hot-swap. Returns a result dict. NEVER raises to the caller for
        a bad model — instead reports rejected=True and keeps last-good."""
        target_dir = Path(new_dir) if new_dir else self.model_dir
        prev = self._model
        try:
            candidate = load_model(target_dir)   # validate fully before swapping
        except ModelLoadError as e:
            self.last_rejected = {
                "model_dir": str(target_dir),
                "reason": str(e),
                "unix": time.time(),
                "kept_version": prev.version,
            }
            # Seal the REJECTION too — the record proves we refused a bad model.
            try:
                record_seal(
                    self.record_dir, "edge_model_rejected",
                    f"theseus-cbm:reject@{int(time.time())}",
                    {"model_dir": str(target_dir), "reason": str(e),
                     "kept_version": prev.version, "kept_sha256": prev.model_sha256},
                )
            except Exception:
                pass  # record sealing must never take the server down
            return {"rejected": True, "reason": str(e),
                    "serving_version": prev.version, "framework": prev.framework}

        # Candidate is valid -> commit the swap.
        with self._lock:
            self._model = candidate
            self.model_dir = target_dir
            self.loaded_unix = time.time()
            self.reload_count += 1

        leaf = None
        try:
            leaf = record_seal(
                self.record_dir, "edge_model_loaded",
                f"theseus-cbm:v{candidate.version}",
                {"version": candidate.version, "framework": candidate.framework,
                 "model_sha256": candidate.model_sha256, "target": candidate.target,
                 "prev_version": prev.version, "model_dir": str(target_dir),
                 "node": "edge", "loaded_unix": self.loaded_unix},
            )
        except Exception as e:
            # Swap succeeded; sealing failed. Surface it but keep serving.
            return {"rejected": False, "swapped": True,
                    "from_version": prev.version, "to_version": candidate.version,
                    "framework": candidate.framework, "sealed": False,
                    "seal_error": str(e)}

        return {"rejected": False, "swapped": True,
                "from_version": prev.version, "to_version": candidate.version,
                "framework": candidate.framework,
                "model_sha256": candidate.model_sha256,
                "sealed": True, "leaf_hash": leaf}


class Handler(BaseHTTPRequestHandler):
    server_version = "TheseusEdge/1.0"
    holder: ModelHolder = None  # set on the server instance below

    # quieter logs (Pi serial console friendly)
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[edge] %s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        if not raw.strip():
            return {}
        return json.loads(raw.decode())

    def do_GET(self) -> None:
        h = self.server.holder
        m = h.model
        if self.path == "/health":
            self._send(200, {
                "status": "ok",
                "model_version": m.version,
                "framework": m.framework,
                "target": m.target,
                "n_features": m.n_features,
                "model_dir": str(h.model_dir),
                "reload_count": h.reload_count,
                "loaded_unix": h.loaded_unix,
                "gpu": False,
            })
        elif self.path == "/version":
            self._send(200, {
                "version": m.version,
                "framework": m.framework,
                "target": m.target,
                "model_sha256": m.model_sha256,
                "features": m.features,
            })
        else:
            self._send(404, {"error": f"no such path: {self.path}",
                             "paths": ["/health", "/version", "POST /predict",
                                       "POST /reload"]})

    def do_POST(self) -> None:
        h = self.server.holder
        try:
            body = self._read_json()
        except Exception as e:
            self._send(400, {"error": f"invalid JSON body: {e}"})
            return

        if self.path == "/predict":
            m = h.model
            # Single: {"features": {...}}   Batch: {"inputs": [{...}, {...}]}
            if "inputs" in body and isinstance(body["inputs"], list):
                preds = []
                for i, item in enumerate(body["inputs"]):
                    feats = item.get("features", item)
                    try:
                        preds.append(h.predict(feats))
                    except ValueError as e:
                        self._send(422, {"error": f"row {i}: {e}"})
                        return
                self._send(200, {"predictions": preds, "model_version": m.version,
                                 "target": m.target, "count": len(preds)})
                return
            feats = body.get("features", body)
            if not isinstance(feats, dict) or not feats:
                self._send(400, {"error": "body must be {\"features\": {name: value, ...}}",
                                 "expected_features": m.features})
                return
            try:
                pred = h.predict(feats)
            except ValueError as e:
                self._send(422, {"error": str(e), "expected_features": m.features})
                return
            self._send(200, {"prediction": pred, "model_version": m.version,
                             "framework": m.framework, "target": m.target})

        elif self.path == "/reload":
            new_dir = body.get("model_dir")
            result = h.reload(Path(new_dir) if new_dir else None)
            # rejected delivery -> 422 (kept last-good); success -> 200.
            self._send(422 if result.get("rejected") else 200, result)

        else:
            self._send(404, {"error": f"no such path: {self.path}",
                             "paths": ["/health", "/version", "POST /predict",
                                       "POST /reload"]})


def build_server(host: str, port: int, model_dir: Path, record_dir: Path) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.holder = ModelHolder(model_dir, record_dir)
    return httpd


def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS edge inference server (CPU-only, Pi-friendly).")
    ap.add_argument("--host", default=os.environ.get("EDGE_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("EDGE_PORT", "8080")))
    ap.add_argument("--model-dir", default=os.environ.get("MODEL_DIR", str(DEFAULT_MODEL_DIR)),
                    help="directory holding meta.json + model.bin (default: demo/models/current)")
    ap.add_argument("--record-dir", default=os.environ.get("RECORD_DIR", str(DEFAULT_RECORD_DIR)),
                    help="tamper-evident record dir to seal swaps into (default: demo/out/record)")
    a = ap.parse_args()

    try:
        httpd = build_server(a.host, a.port, Path(a.model_dir), Path(a.record_dir))
    except ModelLoadError as e:
        print(f"FATAL: cannot start — model dir invalid: {e}", file=sys.stderr)
        return 2

    m = httpd.holder.model
    print(f"THESEUS edge server · CPU-only · http://{a.host}:{a.port}")
    print(f"  serving v{m.version} ({m.framework}, target={m.target}, "
          f"{m.n_features} features) from {a.model_dir}")
    print(f"  sealing swaps into {a.record_dir}")
    print("  endpoints: GET /health  GET /version  POST /predict  POST /reload")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  shutting down edge server")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
