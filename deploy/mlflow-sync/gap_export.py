#!/usr/bin/env python3
"""THE GAP (output to file) — export a registered model from SHORE to a file
bundle using `mlflow-export-import`, so it can cross an air-gap on removable
media (the BDTS/CANES cross-domain-transfer stand-in).

This is Juan's "output the MLflow client outputs to file" step.

We drive mlflow_export_import.model.export_model.export_model() directly (same
code the `export-model` CLI runs) rather than shelling out, because we apply ONE
runtime shim:

    mlflow 3.14.0 added a `deployment_job_state` field on model versions whose
    value (ModelVersionDeploymentJobState) is not JSON-serializable. The pinned
    mlflow-export-import 1.2.0 does `dict(model_version)` then json.dumps(...),
    which explodes. We wrap io_utils.write_file's json.dumps with a `default=`
    that stringifies any unknown object. This is a version-skew shim, not a
    behavior change to what gets transferred (model artifacts + run are
    unaffected; only the metadata serializer is made tolerant).

Usage:
    MLFLOW_TRACKING_URI=http://127.0.0.1:5097 \
        python gap_export.py --model theseus-cbm --output-dir <bundle>
Prints a JSON line with the bundle path + a deterministic bundle hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import mlflow
import mlflow_export_import.common.io_utils as io_utils
from mlflow_export_import.model.export_model import ModelExporter


def _install_json_shim() -> None:
    """Make io_utils JSON writes tolerant of non-serializable MLflow objects."""
    _orig_dumps = json.dumps

    def _safe_dumps(obj, *a, **kw):
        kw.setdefault("default", str)  # stringify ModelVersionDeploymentJobState etc.
        return _orig_dumps(obj, *a, **kw)

    io_utils.json.dumps = _safe_dumps  # only the module the exporter uses


def _bundle_hash(bundle: Path) -> str:
    """Deterministic SHA-256 over every file in the bundle (sorted by relpath).
    This is the integrity tag we seal into the record so the cross-gap delivery
    is provable end-to-end."""
    h = hashlib.sha256()
    files = sorted(p for p in bundle.rglob("*") if p.is_file())
    for p in files:
        rel = p.relative_to(bundle).as_posix().encode()
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        data = p.read_bytes()
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest(), len(files)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        print("ERROR: MLFLOW_TRACKING_URI not set (must point at SHORE)", file=sys.stderr)
        return 2

    _install_json_shim()
    bundle = Path(args.output_dir)

    mlflow.set_tracking_uri(uri)

    # (1) mlflow-export-import: registry entry + run metadata -> file bundle.
    exporter = ModelExporter(
        mlflow_client=mlflow.MlflowClient(),
        export_run=True,           # bundle the backing run metadata
        export_latest_versions=False,
    )
    exporter.export_model(model_name=args.model, output_dir=str(bundle))

    # (2) MLflow 3.x stores log_model() output in the *logged-model* store, NOT
    # the run's artifact dir — so mlflow-export-import 1.2.0 (run-artifact era)
    # exports empty model artifacts. We additionally pull each version's real
    # model artifacts (MLmodel + model.skops + envs) via the supported client
    # API so the bundle is self-contained and the SHIP can actually load it.
    import mlflow.artifacts as artifacts_api
    client = mlflow.MlflowClient()
    mv_root = bundle / "model_version_artifacts"
    versions = sorted(client.search_model_versions(f"name='{args.model}'"),
                      key=lambda v: int(v.version))
    exported_versions = []
    for v in versions:
        dst = mv_root / f"v{v.version}"
        dst.mkdir(parents=True, exist_ok=True)
        artifacts_api.download_artifacts(
            artifact_uri=f"models:/{args.model}/{v.version}",
            dst_path=str(dst),
        )
        exported_versions.append({"version": int(v.version), "run_id": v.run_id,
                                  "source": v.source})

    # write a manifest into the bundle BEFORE hashing so the hash covers it.
    (bundle / "transfer_manifest.json").write_text(json.dumps({
        "model_name": args.model,
        "source_tracking_uri": uri,
        "exported_versions": exported_versions,
    }, indent=2) + "\n")

    bhash, nfiles = _bundle_hash(bundle)
    out = {
        "ok": True,
        "source_tracking_uri": uri,
        "model_name": args.model,
        "bundle_dir": str(bundle),
        "bundle_files": nfiles,
        "bundle_sha256": bhash,
        "exported_versions": exported_versions,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
