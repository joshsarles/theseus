"""Observation intake. Rule #1: chain-append happens at ingest, BEFORE any judgment.

JSONL path is implemented (the deterministic spine). CoT/UDP is the Day 1 COT-slot
task (typed stub in cot/listener.py); both paths land here.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from .chain import Leaf, LocalHashChain
from .schemas import GeoPoint, VendorDecisionObservation


@dataclass(frozen=True)
class ChainedObservation:
    obs: VendorDecisionObservation
    leaf: Leaf


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_jsonl_line(raw: bytes) -> VendorDecisionObservation:
    """Strict parse; raises on malformed input (caller chains the garbage)."""
    d = json.loads(raw.decode())
    ts_emitted = _parse_dt(d["ts_emitted"])
    # Deterministic observed-time: emitter declares transport delay (fixture realism).
    ts_observed = ts_emitted + timedelta(milliseconds=float(d.get("ts_observed_offset_ms", 50)))
    geo = GeoPoint(**d["geo"]) if d.get("geo") else None
    return VendorDecisionObservation(
        obs_id=d.get("obs_id") or str(uuid.uuid4()),
        ts_emitted=ts_emitted,
        ts_observed=ts_observed,
        source_vendor=d["source_vendor"],
        source_model_id=d["source_model_id"],
        decision_type=d["decision_type"],
        payload=d.get("payload", {}),
        confidence=d.get("confidence"),
        geo=geo,
        classification=d.get("classification", "UNCLASSIFIED"),
        ddil_profile=d.get("ddil_profile", "nominal"),
        upstream_provenance=list(d.get("upstream_provenance", [])),
        model_fingerprint=d.get("model_fingerprint"),
        stale=_parse_dt(d["stale"]) if d.get("stale") else None,
        raw=raw,
    )


class ObservationIngestor:
    def __init__(self, chain: LocalHashChain) -> None:
        self.chain = chain
        self._seen: set[str] = set()

    def ingest(self, raw: bytes) -> ChainedObservation:
        try:
            obs = parse_jsonl_line(raw)
        except Exception as exc:  # malformed input is OBSERVED too
            obs = VendorDecisionObservation(
                obs_id=f"malformed-{uuid.uuid4().hex[:8]}",
                ts_emitted=datetime.now(timezone.utc),
                ts_observed=datetime.now(timezone.utc),
                source_vendor="unknown",
                source_model_id="unknown",
                decision_type="malformed",
                payload={"error": type(exc).__name__, "detail": str(exc)[:120]},
                confidence=None,
                geo=None,
                classification="UNCLASSIFIED",
                ddil_profile="nominal",
                upstream_provenance=[],
                model_fingerprint=None,
                stale=None,
                raw=raw,
            )
        if obs.obs_id in self._seen:  # idempotent on obs_id
            raise ValueError(f"duplicate obs_id {obs.obs_id}")
        self._seen.add(obs.obs_id)
        leaf = self.chain.append("observation", obs.obs_id, raw)
        return ChainedObservation(obs, leaf)


def jsonl_replay(path: Path) -> Iterator[bytes]:
    """Deterministic demo driver: yields exact recorded lines (replay fidelity)."""
    with path.open("rb") as f:
        for line in f:
            line = line.strip()
            if line:
                yield line
