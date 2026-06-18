#!/usr/bin/env python3
"""SHIP step — import the file bundle into the SHIP MLflow registry while the
SHORE server is DOWN (proving the ship is disconnected: nothing it does may
touch shore).

Reads ONLY from the transfer bundle on disk. Two parts, mirroring the export:

  (1) mlflow-export-import restores the run metadata into SHIP (Juan's tool, the
      "push those files to an MLflow server on another machine" step).
  (2) We load the model artifacts that crossed in the bundle and re-log +
      register them on SHIP as `theseus-cbm`, so the SHIP can serve the model
      (`mlflow.pyfunc.load_model("models:/theseus-cbm/<v>")`). This is needed
      because MLflow 3.x keeps log_model() output in the logged-model store,
      which the run-artifact-era exporter does not move on its own.

Usage:
    MLFLOW_TRACKING_URI=http://127.0.0.1:5098 \
        python gap_import.py --model theseus-cbm --bundle <bundle> \
        --experiment-name theseus-shore-to-ship
Prints a JSON line with the SHIP registered name/version.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import mlflow_export_import.common.io_utils as io_utils
from mlflow_export_import.run.import_run import RunImporter


def _install_json_shim() -> None:
    _orig_dumps = json.dumps

    def _safe_dumps(obj, *a, **kw):
        kw.setdefault("default", str)
        return _orig_dumps(obj, *a, **kw)

    io_utils.json.dumps = _safe_dumps


def _import_run_lineage(manifest: dict, bundle: Path, experiment: str) -> dict:
    """Use mlflow-export-import's RunImporter to restore the source RUN (lineage)
    into SHIP — Juan's "push those files to an MLflow server" step.

    NOTE on the registry: mlflow-export-import 1.2.0's ModelImporter cannot
    import an MLflow 3.x registered-model VERSION, because 3.x sets the version
    `source` to `models:/m-<id>` (the logged-model store) while the tool expects
    the 2.x `runs:/<run_id>/...` convention and raises
    "Cannot find run ID ... in source field 'models:/...'". So we use the tool
    for the run lineage (what it CAN do across versions) and do the servable
    registry version from the bundled model artifacts below (authoritative).

    Returns {"ok": bool, "note": str, "dst_run_id": str|None}."""
    try:
        run_dirs = sorted({v["run_id"] for v in manifest["exported_versions"]})
        importer = RunImporter(mlflow_client=mlflow.MlflowClient())
        dst_run_id = None
        for rid in run_dirs:
            run_subdir = bundle / rid
            if (run_subdir / "run.json").exists():
                res = importer.import_run(experiment, str(run_subdir))
                # res may be a Run, a (Run, parent_id) tuple, or a run_id str
                run_obj = res[0] if isinstance(res, (tuple, list)) else res
                dst_run_id = getattr(getattr(run_obj, "info", None), "run_id", None) \
                    or (run_obj if isinstance(run_obj, str) else None)
        return {"ok": dst_run_id is not None,
                "note": "mlflow-export-import RunImporter restored run lineage",
                "dst_run_id": dst_run_id}
    except Exception as e:  # version-skew tolerant; artifact re-log below is authoritative
        return {"ok": False, "note": f"run lineage restore skipped: {e}", "dst_run_id": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--experiment-name", default="theseus-shore-to-ship")
    args = ap.parse_args()

    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        print("ERROR: MLFLOW_TRACKING_URI not set (must point at SHIP)", file=sys.stderr)
        return 2
    mlflow.set_tracking_uri(uri)
    _install_json_shim()

    bundle = Path(args.bundle)
    manifest = json.loads((bundle / "transfer_manifest.json").read_text())

    # (1) restore run lineage via mlflow-export-import (Juan's tool, push-to-server)
    meta_result = _import_run_lineage(manifest, bundle, args.experiment_name)

    # (2) authoritative servable path: register each version from the bundled
    # model artifacts VERBATIM (no skops re-serialization). We log the bundle's
    # MLmodel + model.skops as-is and register from the run URI, so the EXACT
    # model bytes that crossed the gap become the ship's registered version.
    #
    # Why verbatim and not load_model()+log_model(): re-serializing through skops
    # after the RunImporter step in the same process yields a corrupt (354-byte)
    # artifact — skops trusted-type state interaction. Copying the artifacts
    # avoids the round-trip entirely and is the faithful air-gap behavior anyway.
    mlflow.set_experiment(args.experiment_name)
    registered = []
    for ver in manifest["exported_versions"]:
        v = ver["version"]
        art = bundle / "model_version_artifacts" / f"v{v}"
        if not (art / "MLmodel").exists():
            print(f"ERROR: bundle missing MLmodel for v{v}", file=sys.stderr)
            return 3
        with mlflow.start_run(run_name=f"ship-import-v{v}") as run:
            mlflow.log_artifacts(str(art), artifact_path="model")
            model_uri = f"runs:/{run.info.run_id}/model"
        mv = mlflow.register_model(model_uri=model_uri, name=args.model)
        registered.append({"src_version": v, "ship_model_version": int(mv.version),
                           "model_uri": mv.source})

    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{args.model}'")
    ship_version = max(int(x.version) for x in versions)

    out = {
        "ok": True,
        "dest_tracking_uri": uri,
        "model_name": args.model,
        "ship_version": ship_version,
        "registered": registered,
        "metadata_restore": meta_result,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
