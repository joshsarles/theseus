"""Core schemas for THE REFEREE. Stdlib only; AGPL-safe (interfaces/scaffold)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

CLASSIFICATION_ORDER = {"UNCLASSIFIED": 0, "CUI": 1, "SECRET": 2, "TOPSECRET": 3}

Severity = Literal["INFO", "WARN", "BREACH"]


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float
    hae: float | None = None
    ce: float | None = None
    le: float | None = None


@dataclass(frozen=True)
class BBox:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def contains(self, p: GeoPoint) -> bool:
        return (self.lat_min <= p.lat <= self.lat_max) and (
            self.lon_min <= p.lon <= self.lon_max
        )


@dataclass(frozen=True)
class VendorDecisionObservation:
    obs_id: str
    ts_emitted: datetime
    ts_observed: datetime
    source_vendor: str
    source_model_id: str
    decision_type: str  # detection | track | recommendation | llm_summary | malformed
    payload: dict[str, Any]
    confidence: float | None
    geo: GeoPoint | None
    classification: str
    ddil_profile: str
    upstream_provenance: list[str]
    model_fingerprint: str | None
    stale: datetime | None  # CoT-style validity end, if provided
    raw: bytes  # exact bytes as observed (replay fidelity)

    @property
    def latency_ms(self) -> float:
        return (self.ts_observed - self.ts_emitted).total_seconds() * 1000.0


@dataclass(frozen=True)
class AuthorizedParameterPolicy:
    policy_id: str
    version: str
    applies_to: str
    geofence: BBox | None
    confidence_floor: float | None
    latency_sla_ms: int | None
    classification_ceiling: str
    ddil_profiles_allowed: list[str]
    forbidden_classes: list[str]
    forbidden_decision_types: list[str]
    require_provenance: bool
    fail_mode: Literal["closed"] = "closed"


@dataclass(frozen=True)
class PolicyViolation:
    obs_id: str
    policy_id: str
    rule: str
    severity: Severity
    detail: str
    taxonomy_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PolicyDecision:
    obs_id: str
    policy_id: str
    gate: Literal["PASS", "HALT_DEFER_TO_HUMAN"]
    violations: list[PolicyViolation]
