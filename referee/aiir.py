"""AIIR v0.1 emitter — BREACH violation + chain context -> AI Incident Record (stdlib only).

Converts each BREACH-severity PolicyViolation (plus its observation, policy, and chain
leaf) into one AIIR v0.1 record per the vendored normative schema
(`referee/aiir_v0_1.schema.json`, byte-identical to the canonical copy). Records are
side artifacts: they never enter the hash chain and never alter verify/tamper behavior.

Derivation honesty (HONESTY-FIRST — maturity: reference/scaffold):
- Every field is EXTRACTED from referee runtime objects (schemas/policy/chain) or the
  policy fixture file on disk; nothing is invented. `clause_id` is the code's `rule`,
  renamed per the AIIR spec; `payload_sha256` is the SHA-256 of the exact observed raw
  bytes (raw payload stays in the chain leaf, never in the record).
- `record_id` is DETERMINISTICALLY derived from the violation leaf hash
  (uuid bytes = sha256("aiir-record-id|" + leaf_hash)[:16] with RFC-4122 v4 bit
  layout). Replay-stable while upstream chain bytes are stable — NOT random; the
  record says so in `ext`.
- The reference chain is unsigned SHA-256: tamper-EVIDENT, not tamper-proof. The
  record carries that marker in-band (schema const).
- `incident_class` mapping (per AIIR spec, not guessed): `unevaluable_rule` ->
  FAIL_CLOSED_UNEVALUABLE; `confidence_floor`/`latency_sla`/`stale_decision`/
  `ddil_profile` -> MATERIAL_DEGRADATION; all other clauses -> GUARDRAIL_BREACH.
- v0 scope: one record per BREACH-severity violation. Gate HALTs without a BREACH
  (e.g. `malformed`, WARN) are chained but not yet emitted as AIIR — the incident
  definition's HALT-only prong is deferred, stated here rather than silently skipped.
- `validate_structural()` is a stdlib SUBSET check against the vendored schema
  (type/enum/const/pattern/required/additionalProperties/propertyNames/items/
  minItems/min-max/minLength/$defs refs). It is NOT a full JSON-Schema 2020-12
  implementation; run the `jsonschema` package OUTSIDE this repo for full validation.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .chain import Leaf, LocalHashChain
from .schemas import (
    AuthorizedParameterPolicy,
    PolicyDecision,
    PolicyViolation,
    VendorDecisionObservation,
)

SCHEMA_PATH = Path(__file__).resolve().parent / "aiir_v0_1.schema.json"
VERIFIER_ID = "referee-verify/reference-v0"

# Clause -> incident_class map, extracted from the AIIR v0.1 spec's §2224b table.
_DEGRADATION_CLAUSES = {"confidence_floor", "latency_sla", "stale_decision", "ddil_profile"}


def incident_class_for(clause_id: str) -> str:
    if clause_id == "unevaluable_rule":
        return "FAIL_CLOSED_UNEVALUABLE"
    if clause_id in _DEGRADATION_CLAUSES:
        return "MATERIAL_DEGRADATION"
    return "GUARDRAIL_BREACH"


def _utc_z(dt: datetime) -> str:
    """ISO-8601 UTC with mandatory 'Z' suffix (schema pattern-checked)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_id(leaf_hash: str) -> str:
    """Deterministic record id derived from the violation leaf hash (see module docstring)."""
    digest = hashlib.sha256(f"aiir-record-id|{leaf_hash}".encode()).digest()
    return "aiir-" + str(uuid.UUID(bytes=digest[:16], version=4))


def build_record(
    obs: VendorDecisionObservation,
    decision: PolicyDecision,
    violation: PolicyViolation,
    leaf: Leaf,
    *,
    policy: AuthorizedParameterPolicy,
    policy_sha256: str,
    chain_head: str,
    merkle_root: str,
    verify_status: str = "NOT_RUN",
    verify_message: str = "",
    verify_first_bad_leaf: int | None = None,
    report_time: datetime | None = None,
) -> dict:
    """One BREACH violation (+ context) -> one AIIR v0.1 record (plain dict, json-ready)."""
    return {
        "aiir_schema_version": "aiir-incident-record-v0.1",
        "record_id": _record_id(leaf.leaf_hash),
        "incident_class": incident_class_for(violation.rule),
        "incident_time_utc": _utc_z(obs.ts_observed),
        "report_time_utc": _utc_z(report_time or datetime.now(timezone.utc)),
        "system": {
            "vendor": obs.source_vendor,
            "model_id": obs.source_model_id,
            "model_fingerprint": obs.model_fingerprint,
            "deployment_context": None,
        },
        "observation": {
            "obs_id": obs.obs_id,
            "ts_emitted_utc": _utc_z(obs.ts_emitted),
            "ts_observed_utc": _utc_z(obs.ts_observed),
            "decision_type": obs.decision_type,
            "confidence": obs.confidence,
            "ddil_profile": obs.ddil_profile,
            "upstream_provenance": list(obs.upstream_provenance),
            "payload_sha256": hashlib.sha256(obs.raw).hexdigest(),
        },
        "policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.version,
            "policy_sha256": policy_sha256,
        },
        "violations": [
            {
                "clause_id": violation.rule,  # spec rename: code 'rule' -> AIIR 'clause_id'
                "severity": violation.severity,
                "detail": violation.detail,
                "taxonomy_tags": list(violation.taxonomy_tags),
            }
        ],
        "gate_outcome": decision.gate,
        "integrity": {
            "hash_algorithm": "sha256",
            "chain_head": chain_head,
            "merkle_root": merkle_root,
            "leaf_index": leaf.idx,
            "leaf_hash": leaf.leaf_hash,
            "prev_hash": leaf.prev_hash,
            "rfc3161_timestamp": None,  # not yet anchored (flipped live at the event)
            "tamper_evident_not_tamper_proof": True,
        },
        "verify": {
            "status": verify_status,
            "message": verify_message,
            "first_bad_leaf": verify_first_bad_leaf,
            "verifier": VERIFIER_ID,
        },
        "classification": {"level": "UNCLASSIFIED", "banner": None},  # v0 emitter: synthetic fixtures only
        "ext": {
            "forceos.referee/chain_impl": (
                "reference SHA-256 prev-hash chain, unsigned — tamper-evident, not tamper-proof"
            ),
            "forceos.referee/data_provenance": (
                "synthetic fixture data; logical vendors only (no real-vendor claims)"
            ),
            "forceos.referee/record_id_derivation": (
                "deterministic: uuid bytes = sha256('aiir-record-id|' + leaf_hash)[:16], "
                "RFC-4122 v4 bit layout; replay-stable, not random"
            ),
        },
    }


def emit_incident_records(
    breaches: list[tuple[VendorDecisionObservation, PolicyDecision, PolicyViolation, Leaf]],
    *,
    chain: LocalHashChain,
    policy: AuthorizedParameterPolicy,
    policy_path: Path,
    out_dir: Path,
    verify_status: str = "NOT_RUN",
    verify_message: str = "",
    verify_first_bad_leaf: int | None = None,
) -> tuple[list[Path], list[str]]:
    """Write one aiir_*.json side artifact per BREACH. Returns (paths, validation errors)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("aiir_*.json"):  # wipe records from previous runs
        stale.unlink()

    policy_sha256 = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    chain_head = chain.leaves[-1].leaf_hash if chain.leaves else "0" * 64
    merkle_root = chain.merkle_root()
    report_time = datetime.now(timezone.utc)

    paths: list[Path] = []
    errors: list[str] = []
    for obs, decision, violation, leaf in breaches:
        record = build_record(
            obs, decision, violation, leaf,
            policy=policy, policy_sha256=policy_sha256,
            chain_head=chain_head, merkle_root=merkle_root,
            verify_status=verify_status, verify_message=verify_message,
            verify_first_bad_leaf=verify_first_bad_leaf, report_time=report_time,
        )
        errors.extend(f"{leaf.idx}/{violation.rule}: {e}" for e in validate_structural(record))
        path = out_dir / f"aiir_{leaf.idx:03d}_{violation.rule}.json"
        path.write_text(json.dumps(record, indent=2) + "\n")
        paths.append(path)
    return paths, errors


# ---- stdlib structural validation (subset; see module docstring honesty note) ----

_SCHEMA_CACHE: dict | None = None


def _schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(SCHEMA_PATH.read_text())
    return _SCHEMA_CACHE


def _type_ok(value: object, t: str) -> bool:
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    return False


def _check(value: object, schema: dict, defs: dict, path: str, errors: list[str]) -> None:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        _check(value, defs[name], defs, path, errors)

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            errors.append(f"{path}: expected type {types}, got {type(value).__name__}")
            return  # deeper keyword checks are meaningless on the wrong type

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        errors.append(f"{path}: {value!r} does not match pattern {schema['pattern']!r}")
    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        errors.append(f"{path}: shorter than minLength {schema['minLength']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required key {req!r}")
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    errors.append(f"{path}: additional property {k!r} not allowed")
        prop_names = schema.get("propertyNames")
        if prop_names and "pattern" in prop_names:
            for k in value:
                if not re.search(prop_names["pattern"], k):
                    errors.append(f"{path}: key {k!r} violates propertyNames pattern")
        for k, sub in props.items():
            if k in value:
                _check(value[k], sub, defs, f"{path}.{k}", errors)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], defs, f"{path}[{i}]", errors)


def validate_structural(record: dict) -> list[str]:
    """Stdlib subset check against the vendored AIIR v0.1 schema. [] == structurally OK."""
    schema = _schema()
    errors: list[str] = []
    _check(record, schema, schema.get("$defs", {}), "$", errors)
    return errors
