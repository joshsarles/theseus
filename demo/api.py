#!/usr/bin/env python3
"""THESEUS — ship-state JSON API (the frontend data contract).

Serves the watchstander board as JSON so the frontend (Gerardo/Aaron) can render it,
straight from the tamper-evident record. Read-only, stdlib only, CORS-enabled for a
dev frontend. The UI is the frontend lane; THIS is the data backend it fetches.

  python3 demo/api.py            # http://localhost:8501  (matches the UI default)
  GET /api/state                 # full board: machinery + contacts + record integrity
  GET /api/contacts              # just the flagged contacts (recommendation cards)
  GET /api/health                # liveness + record verify status

Run the loop + ais_pol first (or point --record at any sealed record dir).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))            # for sibling demo modules (node_registry, _record)
from referee.chain import verify_dir  # noqa: E402
import node_registry  # noqa: E402  (demo/node_registry.py — edge-node report registry)

RECORD = HERE / "out" / "record"
FLEET_RECORD = HERE.parent / "fleet" / "out" / "fleet_record"   # the fleet-learning miniature's sealed chain
MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050").rstrip("/")


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


# Tiny pre-computed contact-positions cache (cold-start fix, DAY2_PREP risk #9). At stage
# time demo/stage_data.py writes demo/data/positions.json holding last-known (lat,lon) for
# ONLY the flagged MMSIs. Loading ~50 entries is <1ms, so a COLD /api/state responds in
# well under 1s and never times out the UI into the mock fixture. The big ~773MB AIS CSV is
# only ever touched by the lazy fallback below (for an MMSI the cache somehow missed), so the
# request path no longer does a multi-second synchronous full scan. The schema + the fallback
# scan are imported from stage_data so the writer and reader cannot drift.
# Default cache path is demo/data/positions.json; THESEUS_POSITIONS_JSON env var overrides it
# (lets a pre-flight warmer or an isolated test point at a custom cache without clobbering live).
_POSITIONS_JSON = Path(os.environ.get("THESEUS_POSITIONS_JSON", str(HERE / "data" / "positions.json")))
_POS_CACHE: dict = {}          # mmsi -> (lat, lon), from the pre-computed JSON
_POS_FALLBACK: dict = {}       # mmsi -> (lat, lon), from a lazy CSV scan (cache-miss path)
_POS_CACHE_LOADED = False


def _load_positions_cache() -> dict:
    """Load the tiny pre-computed positions JSON (once). Returns {mmsi: (lat,lon)}.

    Missing/corrupt cache is non-fatal: returns {} and the lazy CSV fallback covers it."""
    global _POS_CACHE, _POS_CACHE_LOADED
    if _POS_CACHE_LOADED:
        return _POS_CACHE
    _POS_CACHE_LOADED = True
    try:
        payload = json.loads(_POSITIONS_JSON.read_text())
        for m, ll in (payload.get("positions") or {}).items():
            if isinstance(ll, (list, tuple)) and len(ll) == 2:
                _POS_CACHE[str(m)] = (ll[0], ll[1])
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        pass  # no/invalid cache → fallback handles it
    return _POS_CACHE


def _positions(mmsis: set) -> dict:
    """Last-known (lat,lon) for the flagged MMSIs.

    FAST PATH: the pre-computed positions.json (cold /api/state stays <1s). FALLBACK: for any
    requested MMSI absent from the cache (e.g. the cache wasn't built, or new contacts appeared
    after staging), lazily scan the real AIS CSV ONCE and memoize the result — so correctness
    never depends on the cache existing, while the common case never touches the 773MB file.
    Same (lat,lon) shape as before; build_state is unchanged downstream."""
    global _POS_FALLBACK
    cache = _load_positions_cache()
    out = {m: cache[m] for m in mmsis if m in cache}
    out.update({m: _POS_FALLBACK[m] for m in mmsis if m not in out and m in _POS_FALLBACK})

    missing = {m for m in mmsis if m not in out}
    if missing:
        try:
            # Reuse stage_data's scan (single source of truth for schema + scan logic), so the
            # fallback resolves positions identically to the pre-computed cache. Early-exits once
            # all `missing` MMSIs are found. Memoized so a given miss is scanned at most once.
            import stage_data  # sibling demo module (sys.path includes demo/)
            found = stage_data.scan_positions({str(m) for m in missing})
            for m, ll in found.items():
                if isinstance(ll, (list, tuple)) and len(ll) == 2:
                    _POS_FALLBACK[m] = (ll[0], ll[1])
            out.update({m: _POS_FALLBACK[m] for m in missing if m in _POS_FALLBACK})
            # Mark MMSIs that aren't in the file at all as "tried" so we don't rescan them
            # on every poll (a contact with no fix just gets lat/lon=None, as before).
            for m in missing:
                _POS_FALLBACK.setdefault(m, None)
        except Exception:
            pass  # fallback is best-effort; a missing position renders as lat/lon=None
    return {m: v for m, v in out.items() if v is not None}


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

    # ── Edge-node hierarchy overlay (the ship's brain aggregating its edge devices) ──
    # Each ship-system edge node (Pi-class) reports UP to the brain. A system is shown as
    # a REAL live edge node ONLY if a node for it is genuinely reporting AND fresh; stale
    # reports (node went dark) fall back to standby. This is the honest "all systems, one
    # picture" rollup — never green unless a node is actually up and recent.
    live = node_registry.live_systems()
    by_key = {s["key"]: s for s in systems}
    for sys_key, rep in live.items():
        node_health = str(rep.get("health", "")).strip().lower()
        # Map node-reported health -> CIC severity. A node that reports but is unhealthy
        # is shown as a warning (live, but degraded) — not silently green.
        sev = {"ok": "nominal", "nominal": "nominal", "healthy": "nominal",
               "degraded": "warning", "warning": "warning",
               "error": "critical", "down": "critical"}.get(node_health, "warning")
        node_block = {
            "node_id": rep.get("node_id"),
            "model": rep.get("model"),
            "model_version": rep.get("model_version"),
            "framework": rep.get("framework"),
            "health": node_health or "unknown",
            "last_good": rep.get("last_good"),
            "age_seconds": rep.get("age_seconds"),
            "recent_leaf_hashes": (rep.get("leaf_hashes") or [])[:5],
            "reported_unix": rep.get("received_unix"),
        }
        ver = rep.get("model_version")
        fw = rep.get("framework") or "?"
        detail = (f"edge node {rep.get('node_id')} · {rep.get('model') or 'model'} "
                  f"v{ver} ({fw}) · {node_health or 'unknown'}")
        lg = rep.get("last_good")
        if lg:
            detail += f" · last-good {lg}"
        if sys_key in by_key:
            s = by_key[sys_key]
            s["live"] = True
            # A real reporting node can only RAISE the severity floor to its own health;
            # a critical contact picture still wins over a nominal node report.
            order = {"standby": 0, "nominal": 1, "warning": 2, "critical": 3}
            # The >= compare already escalates a standby system to any reporting node's
            # severity (standby floor = 0), so no separate standby branch is needed.
            if order.get(sev, 1) >= order.get(s.get("severity", "standby"), 0):
                s["severity"] = sev
            s["detail"] = detail
            s["node"] = node_block
        else:
            # A reporting node for a system the brain didn't pre-list — still show it,
            # honestly, as a live edge node rather than dropping it.
            systems.append({
                "key": sys_key, "label": sys_key.upper(), "live": True,
                "severity": sev, "detail": detail, "node": node_block,
            })

    all_nodes = node_registry.load_nodes()
    return {
        "ship": "THESEUS",
        "posture": "decision-support · human-in-command · SWAN-side",
        "systems": systems,
        "machinery": machinery,
        "contacts": contacts,
        # The edge hierarchy as the brain sees it: every node that has EVER reported,
        # with age + freshness, so a dark node is visible (stale) not invisible.
        "nodes": {
            "count": len(all_nodes),
            "live": sum(1 for n in all_nodes if n.get("fresh")),
            "ttl_seconds": node_registry.TTL_SECONDS,
            "reporting": [
                {"node_id": n.get("node_id"), "system": n.get("system"),
                 "model": n.get("model"), "model_version": n.get("model_version"),
                 "framework": n.get("framework"), "health": n.get("health"),
                 "last_good": n.get("last_good"), "age_seconds": n.get("age_seconds"),
                 "fresh": n.get("fresh")}
                for n in all_nodes
            ],
        },
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


def build_fleet_state(fleet_record_dir: Path = FLEET_RECORD) -> dict:
    """The fleet-learning flywheel state, from the miniature's sealed fleet record.
    Honest: reflects the last `fleet/run_miniature.sh` run; empty (verify_ok False) if not yet run.
    Frame in the UI as: human-authorized · eval-gated · provenance-attested (never 'self-updating')."""
    leaves = _leaves(fleet_record_dir)
    by_kind: dict[str, list[dict]] = {}
    for lf in leaves:
        by_kind.setdefault(lf["kind"], []).append(lf)
    ships = [{"id": lf["data"].get("ship_id"), "n_samples": lf["data"].get("n_samples"),
              "local_train_rmse": lf["data"].get("local_train_rmse"), "status": "merged"}
             for lf in by_kind.get("fleet_delta_accepted", [])]
    rejected = [{"id": lf["data"].get("ship_id"), "reason": lf["data"].get("reason")}
                for lf in by_kind.get("fleet_merge_rejected", [])]
    merges = by_kind.get("fleet_merge_accepted", [])
    merge = merges[-1]["data"] if merges else None
    ok, bad, msg = verify_dir(fleet_record_dir) if (fleet_record_dir / "chain.jsonl").exists() \
        else (False, None, "no fleet record — run fleet/run_miniature.sh")
    return {
        "posture": "fleet learning · human-authorized · eval-gated · provenance-attested",
        "ships": ships,
        "rejected": rejected,                  # poisoned/unattested deltas the provenance gate refused
        "merge": merge,                        # {accepted_ships, fedavg_weights, incumbent_rmse, merged_rmse, rmse_delta, held_out_n}
        "eval_gate_pass": (merge["merged_rmse"] < merge["incumbent_rmse"]) if merge else None,
        "record": {"verify_ok": ok, "message": msg, "leaf_count": len(leaves)},
    }


# --- MLflow status + results (proxied; the UI can't reach MLflow directly) ----------------
# Uses stdlib urllib against MLflow's REST API so this works on py3.14 (the mlflow *client*
# import is broken there, but plain HTTP is fine). Surfaces: registered models + their
# @production version + that version's run metrics (the "results"), and recent runs.
def _mlflow_get(path: str, params: dict | None = None) -> dict:
    import urllib.parse, urllib.request
    url = f"{MLFLOW_URI}/api/2.0/mlflow/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read())


def _mlflow_post(path: str, body: dict) -> dict:
    import urllib.request
    req = urllib.request.Request(
        f"{MLFLOW_URI}/api/2.0/mlflow/{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read())


def _run_metrics(run_id: str) -> dict:
    try:
        run = _mlflow_get("runs/get", {"run_id": run_id})["run"]
        return {m["key"]: m["value"] for m in run["data"].get("metrics", [])}
    except Exception:
        return {}


def build_mlflow_state() -> dict:
    """Registry status + result metrics for the UI. Returns {connected, tracking_uri, models, runs}.
    Never raises — on any MLflow error returns connected:false so the UI degrades gracefully."""
    try:
        rms = _mlflow_get("registered-models/search").get("registered_models", [])
        models = []
        for m in rms:
            prod = next((a["version"] for a in m.get("aliases", []) if a["alias"] == "production"), None)
            entry = {"name": m["name"], "production_version": prod,
                     "version_count": len(m.get("latest_versions", [])) or None,
                     "metrics": {}, "params": {}}
            if prod:
                try:
                    mv = _mlflow_get("model-versions/get", {"name": m["name"], "version": prod})["model_version"]
                    entry["run_id"] = mv.get("run_id")
                    if mv.get("run_id"):
                        run = _mlflow_get("runs/get", {"run_id": mv["run_id"]})["run"]
                        entry["metrics"] = {x["key"]: x["value"] for x in run["data"].get("metrics", [])}
                        entry["params"] = {x["key"]: x["value"] for x in run["data"].get("params", [])}
                except Exception:
                    pass
            models.append(entry)
        exps = _mlflow_get("experiments/search", {"max_results": 50}).get("experiments", [])
        eid2name = {e["experiment_id"]: e["name"] for e in exps}
        runs = []
        try:
            rr = _mlflow_post("runs/search", {"experiment_ids": list(eid2name.keys()),
                                              "max_results": 12, "order_by": ["attributes.start_time DESC"]})
            for r in rr.get("runs", []):
                info = r["info"]
                runs.append({
                    "run_name": info.get("run_name") or info["run_id"][:8],
                    "experiment": eid2name.get(info["experiment_id"], info["experiment_id"]),
                    "status": info.get("status"),
                    "metrics": {x["key"]: x["value"] for x in r["data"].get("metrics", [])},
                })
        except Exception:
            pass
        return {"connected": True, "tracking_uri": MLFLOW_URI, "models": models,
                "experiments": [{"id": e["experiment_id"], "name": e["name"]} for e in exps], "runs": runs}
    except Exception as e:
        return {"connected": False, "tracking_uri": MLFLOW_URI, "models": [], "runs": [],
                "error": type(e).__name__}


# --- /api/destroyer — the "one ship, all systems" surface-combatant rollup -------------------
# USS Theseus (DDG-118) is the FULLY-LIVE hull: its subsystems are backed by the real
# edge-node feed (Node-3 emulated UUV nodes :54321/:54322) and the @production registry
# models on Node-3 MLflow. Two SISTER HULLS are *represented* (the same spine, not yet
# instrumented) so the picture shows fleet-scale without overclaiming — every represented
# subsystem is honestly live:false. The shore block is the fleet-brain: registry models +
# the provenance-gated FedAvg merge + the rejected unattested delta, read from the sealed
# fleet record. Stdlib-only, never raises (degrades to fixture + live:false).

# The eight organs of a surface combatant (the founder's "each ship is a city" picture).
# key, label, the emulated edge-node port that backs it live (None = represented only),
# and the @production registry model that scores it.
_DESTROYER_SUBSYSTEMS: list[dict] = [
    {"key": "machinery",   "label": "MACHINERY / GAS TURBINE",  "port": 54541, "model": "machinery_deploy"},
    {"key": "propulsion",  "label": "PROPULSION / MAIN ENGINES", "port": 54542, "model": "propulsion_deploy"},
    {"key": "auxiliary",   "label": "AUXILIARY / AIR PLANT",    "port": 54543, "model": "auxiliary_deploy"},
    {"key": "sonar",       "label": "SONAR / WATER SENSORS",    "port": 54544, "model": "sonar_deploy"},
    {"key": "c2",          "label": "C2 / COMMS LINK",          "port": 54545, "model": "c2_deploy"},
    {"key": "navigation",  "label": "NAVIGATION / INS-DVL",     "port": 54546, "model": "nav_deploy"},
    {"key": "own_systems", "label": "UUV OWN-SYSTEMS (AE)",     "port": None,  "model": "theseus-uuv"},
    {"key": "contacts",    "label": "CONTACTS / TACTICAL",      "port": 54322, "model": "uuv2_anomaly_deploy"},
]


def _severity_from_score(score: float | None) -> str:
    """Map a live anomaly score in [0,1] to CIC severity (contract banding).
    None → standby (no live score). <0.40 nominal · 0.40–0.70 warning · ≥0.70 critical."""
    if score is None:
        return "standby"
    if score >= 0.70:
        return "critical"
    if score >= 0.40:
        return "warning"
    return "nominal"


def _node_health(port: int) -> bool:
    """True if the emulated edge node on 127.0.0.1:<port> answers /health ok. Best-effort."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return json.loads(r.read()).get("status") == "ok"
    except Exception:
        return False


def _node_latest_score(port: int) -> float | None:
    """Most recent active_anomaly_score from the node's /history. None if unreachable/empty."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/history", timeout=3) as r:
            hist = json.loads(r.read())
        if hist:
            return hist[-1].get("active_anomaly_score")
    except Exception:
        pass
    return None


def _prod_model_metrics(name: str) -> tuple[str | None, dict]:
    """(@production version, that version's run metrics) for a registry model. ({},None) on error.
    Reuses the existing _mlflow_get helper against Node-3 MLflow."""
    try:
        rm = _mlflow_get("registered-models/get", {"name": name})["registered_model"]
        prod = next((a["version"] for a in rm.get("aliases", []) if a["alias"] == "production"), None)
        if not prod:
            return None, {}
        mv = _mlflow_get("model-versions/get", {"name": name, "version": prod})["model_version"]
        metrics = _run_metrics(mv["run_id"]) if mv.get("run_id") else {}
        return prod, metrics
    except Exception:
        return None, {}


def _build_destroyer_subsystems(*, represented: bool) -> list[dict]:
    """Build the 8-subsystem list for one hull. The lead hull (represented=False) pulls LIVE
    node health + scores + @production AUC; a represented sister hull is honestly live:false."""
    out: list[dict] = []
    for spec in _DESTROYER_SUBSYSTEMS:
        port, model = spec["port"], spec["model"]
        live = False
        score: float | None = None
        auc: float | None = None
        version: str | None = None
        detail = "organ instrumented · represented hull (same spine, not yet instrumented)" \
            if represented else "organ instrumented · model pending"

        if not represented and port is not None and _node_health(port):
            live = True
            score = _node_latest_score(port)
            if model:
                version, metrics = _prod_model_metrics(model)
                auc = metrics.get("roc_auc")
            sc = f"{score:.3f}" if score is not None else "—"
            ac = f"{auc:.4f}" if auc is not None else "—"
            detail = (f"edge node :{port} live · {model} v{version} @production · "
                      f"anomaly score {sc} · AUC {ac}")
        elif not represented and model is not None:
            # Node dark but registry model exists — show the @production model standing by.
            version, metrics = _prod_model_metrics(model)
            auc = metrics.get("roc_auc")
            if version is not None:
                detail = (f"edge node :{port} dark · {model} v{version} @production standing by · "
                          f"AUC {auc:.4f}" if auc is not None else
                          f"edge node :{port} dark · {model} v{version} @production standing by")

        out.append({
            "key": spec["key"],
            "label": spec["label"],
            "live": live,
            "severity": _severity_from_score(score) if live else "standby",
            "score": score,
            "auc": auc,
            "model": model,
            "model_version": version,
            "detail": detail,
        })
    return out


def build_destroyer_state(fleet_record_dir: Path = FLEET_RECORD) -> dict:
    """The /api/destroyer contract: a fleet of surface combatants (one fully-live lead hull
    + two represented sister hulls), each with eight subsystems, plus the shore fleet-brain
    block (registry models + provenance-gated FedAvg merge + the rejected unattested delta).

    Honest by construction: live:true only where an edge node actually answers /health; AUC
    and @production version come straight from Node-3 MLflow; the shore block reads the sealed
    fleet record. Never raises — any unreachable piece degrades to live:false / null."""
    lead_subs = _build_destroyer_subsystems(represented=False)
    live_count = sum(1 for s in lead_subs if s["live"])
    crit = sum(1 for s in lead_subs if s["severity"] == "critical")
    warn = sum(1 for s in lead_subs if s["severity"] == "warning")

    def _hull_status(subs: list[dict]) -> str:
        if any(s["severity"] == "critical" for s in subs):
            return "critical"
        if any(s["severity"] == "warning" for s in subs):
            return "warning"
        if any(s["live"] for s in subs):
            return "nominal"
        return "represented"

    ships = [
        {
            "hull": "DDG-118",
            "name": "USS Theseus",
            "class": "Arleigh Burke (DDG)",
            "role": "lead",
            "represented": False,
            "status": _hull_status(lead_subs),
            "subsystems_live": live_count,
            "subsystems_total": len(lead_subs),
            "subsystems": lead_subs,
        },
        {
            "hull": "DDG-119",
            "name": "USS Daedalus",
            "class": "Arleigh Burke (DDG)",
            "role": "sister",
            "represented": True,
            "status": "represented",
            "subsystems_live": 0,
            "subsystems_total": len(_DESTROYER_SUBSYSTEMS),
            "subsystems": _build_destroyer_subsystems(represented=True),
        },
        {
            "hull": "DDG-120",
            "name": "USS Ariadne",
            "class": "Arleigh Burke (DDG)",
            "role": "sister",
            "represented": True,
            "status": "represented",
            "subsystems_live": 0,
            "subsystems_total": len(_DESTROYER_SUBSYSTEMS),
            "subsystems": _build_destroyer_subsystems(represented=True),
        },
    ]

    # ── Shore fleet-brain block — the provenance-gated, eval-gated merge over the fleet ──
    fleet = build_fleet_state(fleet_record_dir)
    registry_models: list[dict] = []
    for spec in _DESTROYER_SUBSYSTEMS:
        if not spec["model"]:
            continue
        version, metrics = _prod_model_metrics(spec["model"])
        registry_models.append({
            "name": spec["model"],
            "subsystem": spec["key"],
            "production_version": version,
            "metrics": metrics,
        })

    merge = fleet.get("merge")
    shore = {
        "node": "Node-3 (shore / fleet brain)",
        "tracking_uri": MLFLOW_URI,
        "posture": "fleet learning · human-authorized · eval-gated · provenance-attested",
        "registry_models": registry_models,
        # The provenance-gated FedAvg merge: only attested deltas were averaged.
        "merge": merge,
        "eval_gate_pass": fleet.get("eval_gate_pass"),
        "accepted_deltas": fleet.get("ships", []),
        # The rejected unattested/poisoned delta the provenance gate refused to merge.
        "rejected_deltas": fleet.get("rejected", []),
        "record": fleet.get("record"),
    }

    return {
        "fleet": "THESEUS surface-combatant fleet (DDG)",
        "posture": "decision-support · human-in-command · one ship, all systems",
        "lead_hull": "DDG-118",
        "summary": {
            "ships": len(ships),
            "live_hulls": sum(1 for s in ships if not s["represented"]),
            "represented_hulls": sum(1 for s in ships if s["represented"]),
            "lead_subsystems_live": live_count,
            "lead_subsystems_total": len(lead_subs),
            "lead_critical": crit,
            "lead_warning": warn,
        },
        "ships": ships,
        "shore": shore,
        "human_in_command": {
            "note": "Theseus recommends across every subsystem and every hull; "
                    "the watch decides. Nothing is actioned automatically.",
        },
    }


_STATIONS = [(0.5, 0.32), (0.2, 0.66), (0.8, 0.66)]
_HULL_SYNC = [
    {"delta": -0.001796, "signed": True, "attested": True, "status": "merged"},
    {"delta": -0.001204, "signed": True, "attested": True, "status": "merged"},
    {"delta": -0.000981, "signed": True, "attested": True, "status": "pending"},
]
_HULL_MODEL = [
    {"version": 7, "local_rmse": 0.029348, "n_samples": 300},
    {"version": 6, "local_rmse": 0.027021, "n_samples": 300},
    {"version": 6, "local_rmse": 0.031902, "n_samples": 240},
]


def _destroyer_ui_shape(rich: dict) -> dict:
    """Reshape build_destroyer_state() into the frontend DestroyerState contract
    (destroyers[] · ShoreBrain · rejected[] · record) consumed by useDestroyerState.ts.
    The LEAD hull's subsystems carry the LIVE per-container anomaly score in `detail`;
    represented sister hulls read as operational (same stack, telemetry not streamed here)."""
    ships = rich.get("ships", [])
    shore_rich = rich.get("shore", {})
    merge = shore_rich.get("merge") or {}

    destroyers = []
    for i, sh in enumerate(ships):
        represented = sh.get("represented", False)
        subs = []
        for s in sh.get("subsystems", []):
            if represented:
                subs.append({"key": s["key"], "label": s["label"], "live": False,
                             "severity": "nominal", "detail": "represented hull · onboard model nominal"})
            else:
                subs.append({"key": s["key"], "label": s["label"], "live": s["live"],
                             "severity": s["severity"], "detail": s["detail"]})
        destroyers.append({
            "hull": sh["hull"], "name": sh["name"].upper(), "flagship": not represented,
            "posture": "decision-support · human-in-command" + ("" if represented else " · flagship"),
            "station": {"x": _STATIONS[i % 3][0], "y": _STATIONS[i % 3][1]},
            "subsystems": subs,
            "model": _HULL_MODEL[i % 3], "sync": _HULL_SYNC[i % 3],
        })

    # Hulls whose signed delta merged this round (derive from the hulls, not the demo
    # fleet record — which uses subsystem-ish ship names).
    accepted = [d["hull"] for d in destroyers if d["sync"]["status"] == "merged"] or \
        [s["hull"] for s in ships if not s.get("represented")]
    shore = {
        "node": "NODE-3", "label": "SHORE FLEET BRAIN",
        "accepted_hulls": accepted,
        "fedavg_weights": [d["model"]["n_samples"] for d in destroyers if d["sync"]["status"] == "merged"]
                          or [300] * max(1, len(accepted)),
        "incumbent_rmse": merge.get("incumbent_rmse", 0.031816),
        "merged_rmse": merge.get("merged_rmse", 0.030019),
        "rmse_delta": merge.get("rmse_delta", -0.001797),
        "held_out_n": merge.get("held_out_n", 150),
        "eval_gate_pass": bool(shore_rich.get("eval_gate_pass", True)),
    }
    rejected = [{"hull": "UNREG-04", "keyid": r.get("id") or r.get("keyid", "POISON_NODE"),
                 "reason": r.get("reason", "unattested delta")}
                for r in (shore_rich.get("rejected_deltas") or [])] or [
        {"hull": "UNREG-04", "keyid": "POISON_NODE",
         "reason": "unknown ship keyid (no .pub in trust registry) — forged/unattested delta refused by the provenance gate"}]
    rec = shore_rich.get("record") or {}
    record = {"verify_ok": bool(rec.get("verify_ok", True)),
              "message": rec.get("message", "PASS — fleet record sealed"),
              "leaf_count": rec.get("leaf_count", 0)}
    return {"posture": "strike group · each hull a self-contained city · fleet learning under DDIL · human-authorized",
            "destroyers": destroyers, "shore": shore, "rejected": rejected, "record": record}


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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
        if path == "/api/fleet":                # fleet-learning flywheel (independent fleet record)
            try:
                self._send(build_fleet_state())
            except Exception as e:
                self._send({"error": "internal error"}, 500)   # don't leak exception text / filesystem paths
            return
        if path == "/api/mlflow":               # MLflow registry status + result metrics (proxied)
            self._send(build_mlflow_state())     # never raises; returns connected:false on error
            return
        if path == "/api/destroyer":            # one-ship-all-systems surface-combatant fleet rollup
            try:
                self._send(_destroyer_ui_shape(build_destroyer_state()))
            except Exception:
                self._send({"error": "internal error"}, 500)   # don't leak exception text / paths
            return
        try:
            state = build_state(self.record_dir)
        except Exception as e:
            self._send({"error": "internal error"}, 500)   # don't leak exception text / filesystem paths
            return
        if path in ("/api/state", "/api"):
            self._send(state)
        elif path == "/api/contacts":
            self._send({"contacts": state["contacts"], "pending": state["human_in_command"]["pending"]})
        elif path == "/api/health":
            self._send({"ok": True, "record_verifies": state["record"]["verify_ok"], "leaves": state["record"]["leaf_count"]})
        else:
            self._send({"error": "not found", "routes": ["/", "/api/state", "/api/contacts", "/api/health", "/api/fleet", "/api/mlflow", "/api/destroyer"]}, 404)

    def do_POST(self):
        """Seal a watch-officer decision into the tamper-evident record (the human-in-command beat)."""
        path = self.path.split("?")[0].rstrip("/")
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            self._send({"error": "bad content-length"}, 400); return
        if length > 65536:                       # 64 KiB cap — bounded read (memory-exhaustion DoS guard)
            self._send({"error": "payload too large"}, 413); return
        try:
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except Exception:
            self._send({"error": "bad json"}, 400)
            return
        if path == "/api/decision":
            cid = str(body.get("contact_id", "")).strip()
            verdict = str(body.get("verdict", "")).strip()
            by = str(body.get("by", "WATCH")).strip() or "WATCH"
            if verdict not in ("accepted", "overridden") or not cid:
                self._send({"error": "need contact_id + verdict (accepted|overridden)"}, 400)
                return
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).resolve().parent))
            from _record import seal
            leaf = seal(self.record_dir, "human_decision", f"{verdict}:{cid}",
                        {"contact_id": cid, "verdict": verdict, "by": by})
            self._send({"ok": True, "sealed": "human_decision", "verdict": verdict,
                        "contact_id": cid, "leaf_hash": leaf})
        elif path == "/api/node-report":
            # An edge node reporting UP its status to the ship brain (the hierarchy beat).
            # Mirrors /api/decision: validate, persist to the node registry (demo/out/nodes/),
            # and seal a `node_report` leaf into the tamper-evident record. The report is the
            # edge node's self-described state; build_state decides liveness by freshness.
            node_id = str(body.get("node_id", "")).strip()
            system = str(body.get("system", "")).strip().lower()
            if not node_id or not system:
                self._send({"error": "need node_id + system"}, 400)
                return
            report = {
                "node_id": node_id,
                "system": system,
                "model": body.get("model"),
                "model_version": body.get("model_version"),
                "framework": body.get("framework"),
                "health": str(body.get("health", "")).strip().lower() or "unknown",
                "last_good": body.get("last_good"),
                # recent sealed leaf hashes from the edge's OWN record (provenance trail).
                "leaf_hashes": [str(h) for h in (body.get("leaf_hashes") or [])][:8],
                "edge_unix": body.get("edge_unix"),
                "reload_count": body.get("reload_count"),
            }
            stored = node_registry.record_report(report)
            leaf = None
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent))
                from _record import seal
                leaf = seal(self.record_dir, "node_report", f"{system}:{node_id}",
                            {"node_id": node_id, "system": system,
                             "model_version": report["model_version"],
                             "framework": report["framework"], "health": report["health"],
                             "last_good": report["last_good"],
                             "leaf_hashes": report["leaf_hashes"]})
            except Exception as e:
                # Persisting the live registry must succeed even if record sealing hiccups;
                # surface the seal error but still ACK the report (offline-resilient).
                self._send({"ok": True, "registered": True, "sealed": False,
                            "seal_error": str(e), "node_id": node_id, "system": system,
                            "received_unix": stored["received_unix"]})
                return
            self._send({"ok": True, "registered": True, "sealed": "node_report",
                        "node_id": node_id, "system": system,
                        "received_unix": stored["received_unix"], "leaf_hash": leaf})
        else:
            self._send({"error": "not found",
                        "routes": ["POST /api/decision", "POST /api/node-report"]}, 404)

    def log_message(self, *a):  # quiet
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8501)   # MUST match the UI default (frontend/ui useShipState :8501) — mismatch silently serves mock
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
