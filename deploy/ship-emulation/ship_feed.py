"""Drive the emulated destroyer subsystems with their OWN data (features + live feed).

Each subsystem container runs the same receiver image but loads a different model
(<key>_deploy) and must therefore (a) extract that subsystem's feature set and (b) be fed
records carrying those features. This script does both:

  python3 ship_feed.py features                 # write features.<key>.json (mounted into each node)
  python3 ship_feed.py stream [--interval 2]     # continuously feed every subsystem its real data

The labeled UUV JSON streams (sonar/c2/nav) carry ground-truth -ANOMALY records. The real
CSV streams (machinery/propulsion/auxiliary) are real operational data; we forward real rows
and inject a clearly-labelled synthetic fault every Nth record so the demo shows detections.
stdlib-only, runs on the Mac host, POSTs to each node's /stream-item.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

# key -> (dataset path, base host port). Matches docker-compose.yml + the <key>_deploy models.
SUBSYSTEMS = {
    "machinery":  (REPO / "ingest/out/cbm.csv", 54541),
    "propulsion": (REPO / "ingest/out/cmapss.csv", 54542),
    "auxiliary":  (REPO / "ingest/out/metropt.csv", 54543),
    "sonar":      (REPO / "serve/receiver/data/uuv1-sensors-anom.json", 54544),
    "c2":         (REPO / "serve/receiver/data/uuv1-c2-anom.json", 54545),
    "nav":        (REPO / "serve/receiver/data/uuv1-telemetry-anom.json", 54546),
}
# Each hull's subsystem ports are the base + offset. Sisters are fed too (ports skipped if dark),
# with a per-hull phase + seed so the three destroyers don't show identical anomalies in lockstep.
HULL_OFFSETS = {"DDG-118": 0, "DDG-119": 10, "DDG-120": 20}
SKIP = {"record_id", "vehicle_id", "vehicle_type", "timestamp_utc", "sequence_num"}


def _is_num(v) -> bool:
    if isinstance(v, bool):
        return True
    if isinstance(v, (int, float)):
        return True
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False


def load_records(path: Path) -> list[dict]:
    """Return a list of records with numeric feature fields (+ record_id label if present)."""
    if path.suffix == ".json":
        return json.loads(path.read_text())
    rows = []
    with open(path, newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            rec = {k: float(v) for k, v in row.items() if k and _is_num(v) and k.lower() not in SKIP}
            rec["record_id"] = f"row-{i:05d}"
            rows.append(rec)
    return rows


def numeric_feats(rec: dict) -> list[str]:
    return [k for k, v in rec.items() if k not in SKIP and _is_num(v)]


def cmd_features() -> int:
    for key, (path, _port) in SUBSYSTEMS.items():
        recs = load_records(path)
        feats = numeric_feats(recs[0]) if recs else []
        # Union across first 50 records so we don't miss a sparse column.
        seen = set(feats)
        for r in recs[:50]:
            for k in numeric_feats(r):
                if k not in seen:
                    seen.add(k); feats.append(k)
        out = HERE / f"features.{key}.json"
        out.write_text(json.dumps({"sensors": feats, "all": feats}, indent=2))
        print(f"  {key:11s} {len(feats):2d} features -> {out.name}")
    return 0


def _post(port: int, rec: dict) -> int:
    body = json.dumps({"topic_id": "sensors", "data": [rec]}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/stream-item", body,
                                 {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status


def _inject_fault(rec: dict, rng: random.Random, feats: list[str]) -> dict:
    """Clearly-labelled synthetic fault for the unlabeled CSV streams: spike 1-2 channels 12σ-ish."""
    rec = dict(rec)
    for k in rng.sample(feats, min(2, len(feats))):
        rec[k] = float(rec.get(k, 0.0)) * 1.0 + rng.choice([-1, 1]) * (abs(float(rec.get(k, 1.0))) + 1.0) * rng.uniform(6, 14)
    rec["record_id"] = str(rec.get("record_id", "row")) + "-ANOMALY"
    return rec


def stream_subsystem(key: str, port: int, hull: str, off: int,
                     interval: float, anom_rate: float, stop: threading.Event):
    path = SUBSYSTEMS[key][0]
    recs = load_records(path)
    is_json = path.suffix == ".json"      # json already carries labelled anomalies
    feats = numeric_feats(recs[0]) if recs else []
    rng = random.Random((hash(key) ^ (off * 7919)) & 0xffffffff)   # per-hull seed
    phase = (off * 13) % max(1, len(recs))                          # per-hull phase offset
    i = 0
    sent = 0
    while not stop.is_set():
        base = recs[(i + phase) % len(recs)]
        rec = {k: base[k] for k in feats if k in base}
        rec["record_id"] = base.get("record_id", f"{key}-{i:05d}")
        if not is_json and rng.random() < anom_rate:        # inject labelled synthetic fault into CSV stream
            rec = _inject_fault(rec, rng, feats)
        rec["vehicle_id"] = hull
        try:
            _post(port, rec)
            sent += 1
        except Exception:
            pass            # port dark (sister hull not up) — skip silently
        i += 1
        stop.wait(interval)


def cmd_stream(interval: float, anom_rate: float) -> int:
    targets = [(k, SUBSYSTEMS[k][1] + off, hull, off)
               for hull, off in HULL_OFFSETS.items() for k in SUBSYSTEMS]
    print(f"  feeding up to {len(targets)} subsystem nodes across {len(HULL_OFFSETS)} hulls "
          f"@ 1 rec/{interval:g}s each (dark ports skipped; Ctrl-C to stop)")
    stop = threading.Event()
    threads = [threading.Thread(target=stream_subsystem,
                                args=(k, port, hull, off, interval, anom_rate, stop), daemon=True)
               for (k, port, hull, off) in targets]
    for t in threads:
        t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()
        for t in threads:
            t.join(timeout=2)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Drive the emulated destroyer subsystems with their own data.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("features", help="write features.<key>.json for each subsystem (mounted into nodes)")
    s = sub.add_parser("stream", help="continuously feed every subsystem its real data")
    s.add_argument("--interval", type=float, default=2.0)
    s.add_argument("--anom-rate", type=float, default=0.035, help="synthetic-fault rate for the CSV streams (calm ship; occasional dramatic anomaly)")
    a = ap.parse_args()
    return cmd_features() if a.cmd == "features" else cmd_stream(a.interval, a.anom_rate)


if __name__ == "__main__":
    raise SystemExit(main())
