"""Cursor-on-Target UDP listener (Day 1, COT slot).

Mapping contract: architecture spec §4 — uid→target_id (+ dedupe key), type→class via
prefix map, time/start/stale→timestamps, point→geo, detail/_force_referee_/*→
confidence/model. Output of `cot_xml_to_observation_json` is the decision-JSONL shape
consumed by `referee.intake.parse_jsonl_line` — the CoT path lands in the SAME intake
as the JSONL spine (chain-append at ingest, before any judgment).

Composition (kept out of this module so cot/ stays decoupled from referee/):

    async def ingest(raw: bytes) -> None:
        try:
            line = cot_xml_to_observation_json(raw)
        except Exception:
            line = raw          # garbage is observed byte-exact …
        ingestor.ingest(line)   # … and chained as decision_type="malformed" by intake

    await serve(CotListenerConfig(), ingest)

Malformed datagrams therefore ARE ingested (observability includes garbage): the
translate step is strict and raises; the caller feeds the exact datagram bytes through,
and `referee.intake.ObservationIngestor` wraps them as decision_type="malformed".

`_force_referee_` extension attributes (shared contract with cot/emit.py — the spec's
core trio plus replay-fidelity extras, every one optional; absence ⇒ disclosed default):
  confidence · model_id · fingerprint            (spec §4 core)
  vendor · decision_type · classification · ddil_profile · observed_offset_ms
  provenance (space-separated ids) · adjacent_classes (space-separated)
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import uuid

# SECURITY NOTE — stdlib XML parse is a DELIBERATE placeholder: the defusedxml swap
# (entity-expansion / billion-laughs hardening for a socket that eats arbitrary UDP)
# is deferred to event Day 1 per build plan, when deps are installed on the event
# laptop. Until then this listener is loopback/fixture-only.
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Awaitable, Callable

IngestFn = Callable[[bytes], Awaitable[None]]

EXTENSION_NS = "_force_referee_"

COT_TYPE_PREFIX_MAP = {
    "a-f": "friendly", "a-h": "hostile", "a-n": "neutral", "a-u": "unknown",
}

UNKNOWN_COORD = 9999999.0  # CoT/TAK convention for "not provided" on point fields


@dataclass(frozen=True)
class CotListenerConfig:
    host: str = "0.0.0.0"
    port: int = 4242
    extension_ns: str = EXTENSION_NS


class _CotDatagramProtocol(asyncio.DatagramProtocol):
    """Transport only: enqueue exact datagram bytes; ordering lives in serve()."""

    def __init__(self, queue: asyncio.Queue[bytes]) -> None:
        self._queue = queue

    def datagram_received(self, data: bytes, addr: object) -> None:
        self._queue.put_nowait(data)


async def serve(config: CotListenerConfig, ingest: IngestFn) -> None:
    """Bind UDP, forward each datagram's exact bytes to `ingest`.

    Single consumer ⇒ datagrams are ingested strictly in arrival order, so leaf order
    is deterministic under paced replay. A failing ingest (e.g. duplicate-delivery
    rejection — intake is idempotent on obs_id) is reported and the listener keeps
    serving; one bad packet must never take the observer down. Runs until cancelled.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _CotDatagramProtocol(queue),
        local_addr=(config.host, config.port),
    )
    try:
        while True:
            datagram = await queue.get()
            try:
                await ingest(datagram)
            except Exception as exc:  # noqa: BLE001 — observer survives bad packets
                print(f"  cot ingest error: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        transport.close()


def _class_from_type(cot_type: str) -> str:
    for prefix, cls in COT_TYPE_PREFIX_MAP.items():
        if cot_type == prefix or cot_type.startswith(prefix + "-"):
            return cls
    return "unknown"


def cot_xml_to_observation_json(raw_xml: bytes, extension_ns: str = EXTENSION_NS) -> bytes:
    """Translate one CoT event to the observation JSONL shape (exact-byte raw retained).

    Strict (same posture as `parse_jsonl_line`): raises on anything that is not a
    well-formed CoT event — the caller then chains the exact datagram bytes as
    decision_type="malformed". The original XML is retained byte-exact inside
    payload.cot_raw_b64 (intake's `raw` field will hold the translated JSONL line).
    """
    event = ET.fromstring(raw_xml)  # defusedxml here at the event (see module note)
    if event.tag != "event":
        raise ValueError(f"not a CoT event (root <{event.tag}>)")

    uid = event.attrib.get("uid") or f"cot-{uuid.uuid4().hex[:8]}"
    cot_type = event.attrib.get("type", "")
    ts_emitted = event.attrib["time"]  # KeyError ⇒ malformed, chained by caller
    stale = event.attrib.get("stale")

    # point → geo; CoT unknown-sentinels (9999999.0) map back to None/absent.
    geo: dict[str, float] | None = None
    point = event.find("point")
    if point is not None:
        lat, lon = float(point.attrib["lat"]), float(point.attrib["lon"])
        if abs(lat) <= 90.0 and abs(lon) <= 180.0:
            geo = {"lat": lat, "lon": lon}
            for key in ("hae", "ce", "le"):
                val = float(point.attrib.get(key, UNKNOWN_COORD))
                if val != UNKNOWN_COORD:
                    geo[key] = val

    ext = event.find(f"detail/{extension_ns}")
    ea = dict(ext.attrib) if ext is not None else {}

    # confidence: extension wins; else ce feeds a DISCLOSED proxy (spec §4 note);
    # else None + disclosed. Proxy is a declared placeholder heuristic, not calibration.
    confidence: float | None = float(ea["confidence"]) if "confidence" in ea else None
    confidence_source = "extension"
    if confidence is None and geo is not None and "ce" in geo:
        confidence = round(min(0.99, max(0.05, 1.0 - geo["ce"] / 100.0)), 2)
        confidence_source = "ce_proxy"
    elif confidence is None:
        confidence_source = "absent"

    payload: dict[str, object] = {
        "target_id": uid,
        "cot_type": cot_type,
        "class": _class_from_type(cot_type),
    }
    if "how" in event.attrib:
        payload["how"] = event.attrib["how"]  # m-… ⇒ machine-generated
    if ea.get("adjacent_classes"):
        payload["adjacent_classes"] = ea["adjacent_classes"].split()
    if confidence_source != "extension":
        payload["confidence_source"] = confidence_source
    if ext is None:
        payload["referee_extension"] = "absent"  # disclosed, per spec §4
    payload["cot_raw_b64"] = base64.b64encode(raw_xml).decode()

    out: dict[str, object] = {
        "obs_id": uid,  # uid is the dedupe key (intake is idempotent on obs_id)
        "ts_emitted": ts_emitted,
        "source_vendor": ea.get("vendor", "unknown"),
        "source_model_id": ea.get("model_id", "unknown"),
        "decision_type": ea.get("decision_type", "detection"),
        "payload": payload,
        "confidence": confidence,
        "geo": geo,
        "classification": ea.get("classification", "UNCLASSIFIED"),
        "ddil_profile": ea.get("ddil_profile", "nominal"),
        "upstream_provenance": ea.get("provenance", "").split(),
        "model_fingerprint": ea.get("fingerprint"),
    }
    if "observed_offset_ms" in ea:  # emitter-declared transport delay (replay determinism)
        out["ts_observed_offset_ms"] = float(ea["observed_offset_ms"])
    if stale:
        out["stale"] = stale
    return json.dumps(out).encode()
