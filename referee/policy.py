"""The authorized-parameters gate (Cannonico verbatim).

FAIL-CLOSED: any rule that cannot be evaluated is a BREACH (`unevaluable_rule`).
Advisory-only: the gate signals HALT/DEFER-TO-HUMAN and writes the record; it never
commands the vendor system. Violations are chained alongside observations.
"""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import (
    CLASSIFICATION_ORDER,
    AuthorizedParameterPolicy,
    BBox,
    PolicyDecision,
    PolicyViolation,
    VendorDecisionObservation,
)

TAXONOMY = {  # nine-taxonomy tags arrive via the compliance wheel at the event; seed map here
    "geofence": ["authorized-parameters", "spatial"],
    "confidence_floor": ["confidence-integrity"],
    "latency_sla": ["timeliness"],
    "classification_ceiling": ["handling"],
    "ddil_profile": ["authorized-parameters", "comms"],
    "forbidden_class_adjacency": ["protected-objects"],
    "forbidden_decision_type": ["authority", "human-gate"],
    "provenance_missing": ["provenance"],
    "stale_decision": ["timeliness", "state-desync"],
    "malformed": ["observability"],
    "unevaluable_rule": ["fail-closed"],
}


def load_policy(path: Path) -> AuthorizedParameterPolicy:
    d = json.loads(path.read_text())
    return AuthorizedParameterPolicy(
        policy_id=d["policy_id"],
        version=d["version"],
        applies_to=d.get("applies_to", "vendor:any"),
        geofence=BBox(**d["geofence"]) if d.get("geofence") else None,
        confidence_floor=d.get("confidence_floor"),
        latency_sla_ms=d.get("latency_sla_ms"),
        classification_ceiling=d.get("classification_ceiling", "UNCLASSIFIED"),
        ddil_profiles_allowed=list(d.get("ddil_profiles_allowed", [])),
        forbidden_classes=list(d.get("forbidden_classes", [])),
        forbidden_decision_types=list(d.get("forbidden_decision_types", [])),
        require_provenance=bool(d.get("require_provenance", False)),
    )


def _v(obs_id: str, pol: str, rule: str, sev: str, detail: str) -> PolicyViolation:
    return PolicyViolation(obs_id, pol, rule, sev, detail, TAXONOMY.get(rule, []))  # type: ignore[arg-type]


def evaluate_policy(
    obs: VendorDecisionObservation, policy: AuthorizedParameterPolicy
) -> PolicyDecision:
    v: list[PolicyViolation] = []
    pid = policy.policy_id

    if obs.decision_type == "malformed":
        v.append(_v(obs.obs_id, pid, "malformed", "WARN", "unparseable input observed and chained"))
        return PolicyDecision(obs.obs_id, pid, "HALT_DEFER_TO_HUMAN", v)

    # stale window (CoT-style validity)
    if obs.stale is not None and obs.ts_observed > obs.stale:
        v.append(_v(obs.obs_id, pid, "stale_decision", "WARN",
                    f"observed {obs.ts_observed.isoformat()} after stale {obs.stale.isoformat()}"))

    # geofence (fail-closed: geo required when a fence is set)
    if policy.geofence is not None:
        if obs.geo is None:
            v.append(_v(obs.obs_id, pid, "unevaluable_rule", "BREACH", "geofence set but observation has no geo"))
        elif not policy.geofence.contains(obs.geo):
            v.append(_v(obs.obs_id, pid, "geofence", "BREACH",
                        f"({obs.geo.lat:.4f},{obs.geo.lon:.4f}) outside authorized box"))

    # confidence floor
    if policy.confidence_floor is not None and obs.decision_type != "llm_summary":
        if obs.confidence is None:
            v.append(_v(obs.obs_id, pid, "unevaluable_rule", "BREACH", "confidence floor set but confidence missing"))
        elif obs.confidence < policy.confidence_floor:
            v.append(_v(obs.obs_id, pid, "confidence_floor", "BREACH",
                        f"confidence {obs.confidence:.2f} < floor {policy.confidence_floor:.2f}"))

    # latency SLA
    if policy.latency_sla_ms is not None and obs.latency_ms > policy.latency_sla_ms:
        v.append(_v(obs.obs_id, pid, "latency_sla", "BREACH",
                    f"latency {obs.latency_ms:.0f}ms > SLA {policy.latency_sla_ms}ms"))

    # classification ceiling
    ceil = CLASSIFICATION_ORDER.get(policy.classification_ceiling)
    lvl = CLASSIFICATION_ORDER.get(obs.classification)
    if ceil is None or lvl is None:
        v.append(_v(obs.obs_id, pid, "unevaluable_rule", "BREACH", "unknown classification marking"))
    elif lvl > ceil:
        v.append(_v(obs.obs_id, pid, "classification_ceiling", "BREACH",
                    f"{obs.classification} above ceiling {policy.classification_ceiling}"))

    # DDIL allowlist
    if policy.ddil_profiles_allowed and obs.ddil_profile not in policy.ddil_profiles_allowed:
        v.append(_v(obs.obs_id, pid, "ddil_profile", "BREACH",
                    f"profile '{obs.ddil_profile}' not in authorized set"))

    # forbidden classes (direct or declared-adjacent within sensor CE)
    cls = str(obs.payload.get("class", ""))
    adjacent = {str(a) for a in obs.payload.get("adjacent_classes", [])}
    hit = ({cls} | adjacent) & set(policy.forbidden_classes)
    if hit:
        v.append(_v(obs.obs_id, pid, "forbidden_class_adjacency", "BREACH",
                    f"forbidden class context: {sorted(hit)}"))

    # forbidden decision types (e.g. strike_recommendation must route to the human gate)
    if obs.decision_type in policy.forbidden_decision_types:
        v.append(_v(obs.obs_id, pid, "forbidden_decision_type", "BREACH",
                    f"decision_type '{obs.decision_type}' requires the human gate"))

    # provenance required on imagery-derived decisions
    if policy.require_provenance and obs.decision_type == "detection" and not obs.upstream_provenance:
        v.append(_v(obs.obs_id, pid, "provenance_missing", "BREACH",
                    "imagery-derived decision carries no input provenance"))

    gate = "HALT_DEFER_TO_HUMAN" if any(x.severity == "BREACH" for x in v) else "PASS"
    return PolicyDecision(obs.obs_id, pid, gate, v)  # type: ignore[arg-type]
