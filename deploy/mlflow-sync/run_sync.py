#!/usr/bin/env python3
"""End-to-end SHORE -> SHIP MLflow registry delivery across a simulated DDIL gap.

Implements Juan's BDTS/CANES idea: export the MLflow client outputs to FILE with
`mlflow-export-import`, carry the files across an air-gap (removable-media stand-in),
then push them into an MLflow server on another "machine" — with the source server
DOWN to prove the ship is disconnected.

Steps (each prints PASS/FAIL):
  1. servers up (shore + ship)            -> both healthy
  2. train + register on SHORE            -> theseus-cbm vN registered on shore
  3. shore model loads + predicts         -> proves the source is real
  4. export to file bundle (THE GAP)      -> mlflow-export-import + model artifacts
  5. CUT THE CABLE: stop SHORE            -> shore /health unreachable
  6. import bundle into SHIP (shore down) -> theseus-cbm vM registered on ship
  7. SHIP serves the model                -> pyfunc.load_model + predict on ship
  8. seal "shore_to_ship_sync" + verify   -> record verify_dir PASS

Run:  python run_sync.py        (does NOT clean; appends to record)
      python run_sync.py --fresh (wipe shore/ship/transfer/record first)

All paths come from config.sh values mirrored below so this is the single driver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VPY = HERE / ".venv" / "bin" / "python"
SERVERS = HERE / "servers.sh"

SHORE_URI = "http://127.0.0.1:5097"
SHIP_URI = "http://127.0.0.1:5098"
SHORE_DIR = HERE / "shore"
SHIP_DIR = HERE / "ship"
TRANSFER_DIR = HERE / "transfer"
BUNDLE_DIR = TRANSFER_DIR / "theseus-cbm-bundle"
RECORD_DIR = HERE / "out" / "record"
MODEL_NAME = "theseus-cbm"
SHIP_EXPERIMENT = "theseus-shore-to-ship"

# never trigger the repo-root default mlflow.db, never leak env var names
BASE_ENV = {
    **os.environ,
    "MLFLOW_RECORD_ENV_VARS_IN_MODEL_LOGGING": "false",
    "PYTHONUNBUFFERED": "1",
}


class Step:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))
        self.results.append((name, ok, detail))
        return ok

    def all_ok(self) -> bool:
        return all(ok for _, ok, _ in self.results)


def sh(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env or BASE_ENV)


def server(action: str, name: str = "") -> subprocess.CompletedProcess:
    args = ["bash", str(SERVERS), action] + ([name] if name else [])
    return sh(args)


def health(uri: str) -> bool:
    try:
        with urllib.request.urlopen(uri.rstrip("/") + "/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def run_py(script: str, *args: str, env: dict | None = None) -> tuple[int, str, str]:
    p = sh([str(VPY), str(HERE / script), *args], env=env or BASE_ENV)
    return p.returncode, p.stdout, p.stderr


def last_json_line(stdout: str) -> dict | None:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true",
                    help="wipe shore/ship/transfer/record before running")
    args = ap.parse_args()

    st = Step()
    print("=" * 70)
    print("SHORE -> SHIP MLflow delivery across a DDIL gap (BDTS/CANES pattern)")
    print("=" * 70)

    if args.fresh:
        # stop anything running, then wipe state dirs we own
        server("stop", "shore"); server("stop", "ship")
        for d in (SHORE_DIR, SHIP_DIR, TRANSFER_DIR, RECORD_DIR):
            shutil.rmtree(d, ignore_errors=True)
        print("(fresh) wiped shore/ ship/ transfer/ out/record/")

    # --- step 1: servers up -------------------------------------------------
    server("start", "shore"); server("start", "ship")
    ok = health(SHORE_URI) and health(SHIP_URI)
    st.record("1. servers up (shore:5097 + ship:5098)", ok,
              f"shore={'200' if health(SHORE_URI) else 'down'} ship={'200' if health(SHIP_URI) else 'down'}")
    if not ok:
        return _finish(st)

    # --- step 2: train + register on SHORE ----------------------------------
    env = {**BASE_ENV, "MLFLOW_TRACKING_URI": SHORE_URI}
    rc, out, err = run_py("train_register_shore.py", env=env)
    shore = last_json_line(out)
    ok = rc == 0 and shore and shore.get("ok")
    shore_version = shore["version"] if ok else None
    st.record("2. train + register on SHORE", bool(ok),
              f"{MODEL_NAME} v{shore_version} rmse={shore['rmse']}" if ok else (err.strip().splitlines()[-1] if err.strip() else "no json"))
    if not ok:
        return _finish(st)

    # --- step 3: shore model loads + predicts -------------------------------
    rc, out, err = run_py("verify_side.py", "--side", "shore",
                          "--uri", SHORE_URI, "--version", str(shore_version), env=env)
    sv = last_json_line(out)
    ok = rc == 0 and sv and sv.get("ok")
    st.record("3. SHORE model loads + predicts", bool(ok),
              f"v{shore_version} predict[:3]={sv['predict_head']}" if ok else (err.strip().splitlines()[-1] if err.strip() else "load failed"))
    if not ok:
        return _finish(st)

    # --- step 4: export to file bundle (THE GAP) ----------------------------
    rc, out, err = run_py("gap_export.py", "--model", MODEL_NAME,
                          "--output-dir", str(BUNDLE_DIR), env=env)
    exp = last_json_line(out)
    ok = rc == 0 and exp and exp.get("ok")
    bundle_hash = exp["bundle_sha256"] if ok else None
    st.record("4. export SHORE -> file bundle (mlflow-export-import + artifacts)", bool(ok),
              f"{exp['bundle_files']} files sha256={bundle_hash[:12]}…" if ok else (err.strip().splitlines()[-1] if err.strip() else "export failed"))
    if not ok:
        return _finish(st)

    # --- step 5: CUT THE CABLE — stop SHORE ---------------------------------
    server("stop", "shore")
    shore_down = not health(SHORE_URI)
    st.record("5. CUT THE CABLE: SHORE stopped (ship is now disconnected)", shore_down,
              "shore /health unreachable" if shore_down else "SHORE STILL UP")
    if not shore_down:
        return _finish(st)

    # --- step 6: import bundle into SHIP (shore DOWN) -----------------------
    env_ship = {**BASE_ENV, "MLFLOW_TRACKING_URI": SHIP_URI}
    rc, out, err = run_py("gap_import.py", "--model", MODEL_NAME,
                          "--bundle", str(BUNDLE_DIR),
                          "--experiment-name", SHIP_EXPERIMENT, env=env_ship)
    imp = last_json_line(out)
    ok = rc == 0 and imp and imp.get("ok")
    ship_version = imp["ship_version"] if ok else None
    st.record("6. import bundle -> SHIP registry (with SHORE down)", bool(ok),
              f"{MODEL_NAME} v{ship_version} on ship; meta_restore={imp['metadata_restore']['ok']}" if ok else (err.strip().splitlines()[-1] if err.strip() else "import failed"))
    if not ok:
        return _finish(st)

    # --- step 7: SHIP serves the model --------------------------------------
    rc, out, err = run_py("verify_side.py", "--side", "ship",
                          "--uri", SHIP_URI, "--version", str(ship_version), env=env_ship)
    sv = last_json_line(out)
    ok = rc == 0 and sv and sv.get("ok")
    st.record("7. SHIP serves the model (pyfunc.load_model + predict)", bool(ok),
              f"v{ship_version} predict[:3]={sv['predict_head']}" if ok else (err.strip().splitlines()[-1] if err.strip() else "load failed"))
    if not ok:
        return _finish(st)

    # --- step 8: seal the transfer + verify ---------------------------------
    rc, out, err = run_py("seal_transfer.py",
                          "--model", MODEL_NAME,
                          "--shore-version", str(shore_version),
                          "--ship-version", str(ship_version),
                          "--bundle", str(BUNDLE_DIR),
                          "--bundle-sha256", bundle_hash,
                          "--record-dir", str(RECORD_DIR), env=BASE_ENV)
    seal = last_json_line(out)
    ok = rc == 0 and seal and seal.get("verify_ok")
    st.record("8. seal shore_to_ship_sync + record verify_dir", bool(ok),
              seal["verify_msg"] if ok else (err.strip().splitlines()[-1] if err.strip() else "seal failed"))

    return _finish(st)


def _finish(st: Step) -> int:
    print("-" * 70)
    n_pass = sum(1 for _, ok, _ in st.results if ok)
    n = len(st.results)
    verdict = "PASS" if st.all_ok() else "FAIL"
    print(f"OVERALL: {verdict}  ({n_pass}/{n} steps passed)")
    print("-" * 70)
    return 0 if st.all_ok() else 1


if __name__ == "__main__":
    raise SystemExit(main())
