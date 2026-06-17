"""THESEUS edge serving — model loading + inference core.

Pi-realistic: CPU-only, RAM-light, stdlib by default. The ONLY optional dependency
is scikit-learn, and that is needed solely to *unpickle* a model that was trained
with sklearn (framework == "sklearn"). The pure-stdlib OLS fallback model
(framework == "stdlib-ols") needs nothing beyond the Python standard library, so a
fresh Pi with no wheels can still load + serve that flavor.

A loaded model is fully described by demo/models/current/:
    meta.json   -> {version, framework, target, features[...], rmse, model_sha256, ...}
    model.bin   -> sklearn pickle  OR  stdlib-ols JSON ({bias, weights{feature:coef}})

Inference contract (matches demo/retrain.py): build the feature vector in
meta["features"] order, predict the CBM decay-state coefficient (≈0.95 fouled .. 1.0
clean). We integrity-check model.bin against meta["model_sha256"] on load, so a
truncated / corrupted delivery is rejected BEFORE it can replace last-good.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ModelLoadError(Exception):
    """Raised when a model directory is missing/corrupt/unsupported. Callers keep
    serving last-good on this (DDIL-safe behavior)."""


@dataclass
class LoadedModel:
    """An in-memory, ready-to-serve model + the metadata needed to validate input."""
    version: int
    framework: str
    target: str
    features: list[str]
    rmse: float | None
    model_sha256: str
    source_dir: str
    _predict_fn: Any = field(repr=False, default=None)

    @property
    def n_features(self) -> int:
        return len(self.features)

    def predict(self, feature_map: dict[str, float]) -> float:
        """Predict from a {feature_name: value} map. Missing features -> error."""
        missing = [f for f in self.features if f not in feature_map]
        if missing:
            raise ValueError(f"missing features: {missing[:8]}"
                             f"{' …' if len(missing) > 8 else ''}")
        try:
            vec = [float(feature_map[f]) for f in self.features]
        except (TypeError, ValueError) as e:
            raise ValueError(f"non-numeric feature value: {e}") from e
        return float(self._predict_fn(vec))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_sklearn_predict(blob: bytes):
    """Unpickle an sklearn estimator and return a fn(vector)->float.

    Only imported when framework == 'sklearn', so a stdlib-ols-only Pi never needs
    scikit-learn installed."""
    try:
        import pickle  # stdlib, cheap
        model = pickle.loads(blob)
    except Exception as e:  # ModuleNotFoundError (no sklearn), unpickle error, etc.
        raise ModelLoadError(f"cannot unpickle sklearn model: {e}") from e
    if not hasattr(model, "predict"):
        raise ModelLoadError("unpickled object has no .predict()")

    def _fn(vec: list[float]) -> float:
        return float(model.predict([vec])[0])

    return _fn


def _build_stdlib_ols_predict(blob: bytes, features: list[str]):
    """Pure-stdlib linear model: prediction = bias + Σ weight_i · x_i.

    Matches the artifact demo/retrain.py writes in its no-sklearn fallback path:
        {"framework": "stdlib-ols", "bias": <float>, "weights": {feature: coef, ...}}
    """
    try:
        art = json.loads(blob.decode())
    except Exception as e:
        raise ModelLoadError(f"cannot parse stdlib-ols artifact: {e}") from e
    bias = float(art["bias"])
    weights = art["weights"]
    # Freeze the coefficient order to the meta feature order.
    coefs = [float(weights[f]) for f in features]

    def _fn(vec: list[float]) -> float:
        return bias + sum(w * x for w, x in zip(coefs, vec))

    return _fn


def load_model(model_dir: Path | str) -> LoadedModel:
    """Load + integrity-verify a model directory (demo/models/current/ shape).

    Raises ModelLoadError on anything wrong (missing files, bad json, sha mismatch,
    unsupported framework, unpicklable blob). The serve layer treats any
    ModelLoadError as "reject this delivery, keep last-good."
    """
    model_dir = Path(model_dir)
    meta_path = model_dir / "meta.json"
    bin_path = model_dir / "model.bin"
    if not meta_path.exists():
        raise ModelLoadError(f"no meta.json in {model_dir}")
    if not bin_path.exists():
        raise ModelLoadError(f"no model.bin in {model_dir}")

    try:
        meta = json.loads(meta_path.read_text())
    except Exception as e:
        raise ModelLoadError(f"meta.json is not valid JSON: {e}") from e

    for key in ("version", "framework", "features", "model_sha256"):
        if key not in meta:
            raise ModelLoadError(f"meta.json missing required key '{key}'")

    features = meta["features"]
    if not isinstance(features, list) or not features:
        raise ModelLoadError("meta.json 'features' must be a non-empty list")

    # Integrity: the bytes we are about to load must match the sha sealed at train time.
    actual_sha = _sha256_file(bin_path)
    if actual_sha != meta["model_sha256"]:
        raise ModelLoadError(
            f"model.bin sha256 mismatch (meta={meta['model_sha256'][:12]}… "
            f"actual={actual_sha[:12]}…) — corrupt/tampered delivery")

    blob = bin_path.read_bytes()
    framework = meta["framework"]
    if framework == "sklearn":
        predict_fn = _build_sklearn_predict(blob)
    elif framework == "stdlib-ols":
        predict_fn = _build_stdlib_ols_predict(blob, features)
    else:
        raise ModelLoadError(f"unsupported framework '{framework}'")

    return LoadedModel(
        version=int(meta["version"]),
        framework=framework,
        target=meta.get("target", "unknown"),
        features=features,
        rmse=meta.get("rmse"),
        model_sha256=meta["model_sha256"],
        source_dir=str(model_dir),
        _predict_fn=predict_fn,
    )
