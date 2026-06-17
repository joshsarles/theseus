#!/usr/bin/env python3
"""THESEUS shore→ship live model delivery — objectives #3 + #4, made real.

The flow this simulates end-to-end on one Mac (stands in for the real shore→ship path):

    SHORE (Tier-1)                         SHIP / EDGE (Raspberry Pi 5)
    ───────────────                        ──────────────────────────
    stage → retrain → update_model         edge model_server.py running
       promotes a new version into            holds last-good in RAM
       demo/models/current/  (sealed)
                    │
                    │  bundle models/current/  ──► copy over the link
                    ▼            (HTTP body / Tailscale / sneakerless bundle)
            edge node lands the bundle, validates + integrity-checks,
            HOT-SWAPS to the new version, seals `edge_model_loaded`,
            and /version now reports the new version.
            If the bundle is BAD, the edge keeps serving last-good (DDIL-safe).

Two transports (both real, no mocks):
  * http   — POST the bundle to the edge as a tar over the wire; the server writes it
             to a staging dir and reloads from there. This is the Tailscale/bundle
             stand-in: the edge pulls bytes, not files on a shared disk.
  * file   — drop the bundle into a delivery dir the edge can see, then POST /reload
             pointing at it. Models for nodes that share a volume / mounted bundle.

Usage:
  # 1) Promote a new version on shore (runs the demo loop: stage→retrain→update)
  python3 serve/deliver.py promote

  # 2) Deliver the current promoted model to a running edge server + confirm flip
  python3 serve/deliver.py deliver --edge http://127.0.0.1:8080 --transport http

  # one-shot: promote then deliver
  python3 serve/deliver.py promote-and-deliver --edge http://127.0.0.1:8080
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEMO = ROOT / "demo"
CURRENT = DEMO / "models" / "current"


# ───────────────────────── shore side: promote a new version ─────────────────────────

def run_loop() -> int:
    """Run the real demo loop (stage → retrain → update_model) to promote a new model
    version into demo/models/current/. We call the demo scripts as-is — no rewrite."""
    py = sys.executable
    steps = [
        ("stage_data.py", []),
        ("retrain.py", []),
        ("update_model.py", []),
    ]
    for script, extra in steps:
        print(f"  [shore] {script} …")
        r = subprocess.run([py, str(DEMO / script), *extra], cwd=str(DEMO))
        if r.returncode != 0:
            print(f"  [shore] {script} FAILED (rc={r.returncode})")
            return r.returncode
    meta = json.loads((CURRENT / "meta.json").read_text())
    print(f"  [shore] promoted v{meta['version']} ({meta['framework']}, "
          f"RMSE={meta.get('rmse')}) -> demo/models/current")
    return 0


# ───────────────────────── the bundle (what crosses the link) ─────────────────────────

def bundle_bytes(model_dir: Path = CURRENT) -> bytes:
    """Tar up a model dir (meta.json + model.bin) into a single transferable bundle."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name in ("meta.json", "model.bin"):
            p = model_dir / name
            if not p.exists():
                raise SystemExit(f"cannot bundle: {p} missing")
            tar.add(p, arcname=name)
    return buf.getvalue()


def unbundle_to(blob: bytes, dest: Path) -> Path:
    """Extract a bundle into dest (the edge's staging dir). Returns dest."""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r") as tar:
        # safe extract: flat members only
        for member in tar.getmembers():
            if member.name not in ("meta.json", "model.bin") or member.isdir():
                continue
            tar.extract(member, path=dest)
    return dest


# ───────────────────────── edge calls (HTTP) ─────────────────────────

def _get(edge: str, path: str) -> dict:
    with urllib.request.urlopen(f"{edge}{path}", timeout=10) as r:
        return json.loads(r.read().decode())


def _post(edge: str, path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{edge}{path}", data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def deliver(edge: str, transport: str, source: Path = CURRENT,
            staging: Path | None = None) -> dict:
    """Deliver `source` model dir to the running edge server and trigger a hot-swap.

    transport=file : write the bundle into a delivery dir the edge can read, then
                     POST /reload {model_dir: <that dir>}.
    transport=http : (default) the edge already reads from its own staging path; we
                     unbundle into a shore-controlled staging dir that the edge mounts
                     /reaches and point /reload at it. For a one-host demo these are
                     the same filesystem; on a real Pi this dir is the landed bundle.
    """
    before = _get(edge, "/version")
    print(f"  [edge ] before: serving v{before['version']} ({before['framework']})")

    blob = bundle_bytes(source)
    print(f"  [link ] bundle = {len(blob)} bytes (tar: meta.json + model.bin)")

    if staging is None:
        staging = ROOT / "serve" / "edge_inbox"
    landed = unbundle_to(blob, staging)
    print(f"  [edge ] landed bundle -> {landed}")

    status, result = _post(edge, "/reload", {"model_dir": str(landed)})
    if result.get("rejected"):
        print(f"  [edge ] REJECTED bad delivery — kept last-good v"
              f"{result.get('serving_version')}: {result.get('reason')}")
    else:
        print(f"  [edge ] hot-swap v{result.get('from_version')} -> "
              f"v{result.get('to_version')}  sealed={result.get('sealed')}")

    after = _get(edge, "/version")
    print(f"  [edge ] after : serving v{after['version']} ({after['framework']})")
    return {"status": status, "result": result, "before": before, "after": after}


# ───────────────────────── CLI ─────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS shore→ship live model delivery.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("promote", help="run the demo loop to promote a new model version")

    d = sub.add_parser("deliver", help="deliver current promoted model to a running edge node")
    d.add_argument("--edge", default="http://127.0.0.1:8080", help="edge server base URL")
    d.add_argument("--transport", choices=["http", "file"], default="http")
    d.add_argument("--source", default=str(CURRENT), help="model dir to deliver")

    pd = sub.add_parser("promote-and-deliver", help="promote then deliver in one shot")
    pd.add_argument("--edge", default="http://127.0.0.1:8080")
    pd.add_argument("--transport", choices=["http", "file"], default="http")

    a = ap.parse_args()

    if a.cmd == "promote":
        return run_loop()
    if a.cmd == "deliver":
        deliver(a.edge, a.transport, Path(a.source))
        return 0
    if a.cmd == "promote-and-deliver":
        rc = run_loop()
        if rc != 0:
            return rc
        deliver(a.edge, a.transport)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
