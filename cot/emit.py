"""Demo vendor-side CoT emitter (Day 1, COT slot). OPEN helper.

Reads cached model decisions (JSONL — the fixtures/gen_smoke.py shape) and emits them
as MITRE Cursor-on-Target XML over UDP at a configurable realtime factor, with the
Referee fields in the `_force_referee_` detail extension. Used by the three demo
"vendors" (detector-v1/v2/v3). Inverse of cot/listener.py's spec-§4 mapping; the
extension attribute set is documented there (shared contract).

Replay fidelity rules:
  - Lines that cannot be rendered as CoT (the fixture's malformed tail) are sent as
    RAW bytes, byte-exact — the listener side observes and chains the garbage.
  - `event@uid` carries the decision id (obs_id): intake dedupes on it, so the uid
    must be unique per decision, not per track.
  - Pacing follows recorded ts_emitted deltas divided by realtime_factor
    (8.0 ⇒ 8s of mission time per wall second). Recorded-inference deterministic
    replay, honestly labeled.

Run: python -m cot.emit --source fixtures/smoke_25.jsonl --speed 8
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import uuid
import xml.etree.ElementTree as ET  # build-only here; parse hardening is the listener's job
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .listener import COT_TYPE_PREFIX_MAP, EXTENSION_NS, UNKNOWN_COORD

ROOT = Path(__file__).resolve().parent.parent

# class → affiliation prefix (inverse of the listener map). Vendor classes beyond
# affiliation (vehicle/person/…) ride as unknown-affiliation; CoT speaks affiliation
# at the prefix level, finer class detail does not survive the CoT hop by design.
AFFILIATION_PREFIX = {cls: prefix for prefix, cls in COT_TYPE_PREFIX_MAP.items()}

DEFAULT_STALE_WINDOW_S = 120.0  # CoT requires @stale; default validity when unset


@dataclass(frozen=True)
class EmitterConfig:
    source_jsonl: Path
    target_host: str = "127.0.0.1"
    target_port: int = 4242
    realtime_factor: float = 8.0


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _zulu(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coord(val: object) -> str:
    return str(float(val)) if isinstance(val, (int, float)) else str(UNKNOWN_COORD)


def _type_from_class(cls: str) -> str:
    return f"{AFFILIATION_PREFIX.get(cls, 'a-u')}-G"  # -G: ground (HIT-UAV objects)


def observation_json_to_cot_xml(line: bytes) -> bytes:
    """Inverse of listener mapping (spec §4).

    Strict (mirrors `parse_jsonl_line`'s required fields): raises on lines that do
    not carry a renderable decision — run() then replays those byte-exact so the
    observer still sees the garbage.
    """
    d = json.loads(line.decode())
    ts_emitted = _parse_dt(str(d["ts_emitted"]))
    vendor = str(d["source_vendor"])
    model_id = str(d["source_model_id"])
    decision_type = str(d["decision_type"])
    payload = d.get("payload") or {}

    uid = str(d.get("obs_id") or payload.get("target_id") or f"cot-{uuid.uuid4().hex[:8]}")
    cot_type = str(payload.get("cot_type") or _type_from_class(str(payload.get("class", ""))))
    time_attr = _zulu(ts_emitted)
    stale_attr = (
        _zulu(_parse_dt(str(d["stale"])))
        if d.get("stale")
        else _zulu(ts_emitted + timedelta(seconds=DEFAULT_STALE_WINDOW_S))
    )

    event = ET.Element("event", {
        "version": "2.0",
        "uid": uid,
        "type": cot_type,
        "how": "m-g",  # machine-generated (spec §4 machine-origin flag)
        "time": time_attr,
        "start": time_attr,
        "stale": stale_attr,
    })

    geo = d.get("geo") or {}
    ET.SubElement(event, "point", {
        "lat": _coord(geo.get("lat")),
        "lon": _coord(geo.get("lon")),
        "hae": _coord(geo.get("hae")),
        "ce": _coord(geo.get("ce")),
        "le": _coord(geo.get("le")),
    })

    ext_attrs: dict[str, str] = {
        "vendor": vendor,
        "model_id": model_id,
        "decision_type": decision_type,
        "classification": str(d.get("classification", "UNCLASSIFIED")),
        "ddil_profile": str(d.get("ddil_profile", "nominal")),
    }
    if d.get("confidence") is not None:
        ext_attrs["confidence"] = str(float(d["confidence"]))
    if d.get("model_fingerprint"):
        ext_attrs["fingerprint"] = str(d["model_fingerprint"])
    if d.get("ts_observed_offset_ms") is not None:
        ext_attrs["observed_offset_ms"] = str(float(d["ts_observed_offset_ms"]))
    provenance = [str(p) for p in d.get("upstream_provenance", [])]
    if provenance:  # ids are token-shaped (frame-sha256:…); space-separated by contract
        ext_attrs["provenance"] = " ".join(provenance)
    adjacent = [str(a) for a in payload.get("adjacent_classes", [])]
    if adjacent:
        ext_attrs["adjacent_classes"] = " ".join(adjacent)

    detail = ET.SubElement(event, "detail")
    ET.SubElement(detail, EXTENSION_NS, ext_attrs)
    return ET.tostring(event, encoding="utf-8", xml_declaration=True)


def run(config: EmitterConfig) -> None:
    """Replay loop: JSONL line → CoT datagram → UDP sendto, paced by recorded deltas."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent = passthrough = 0
    prev_ts: datetime | None = None
    try:
        with config.source_jsonl.open("rb") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                ts: datetime | None = None
                try:
                    datagram = observation_json_to_cot_xml(line)
                    ts = _parse_dt(str(json.loads(line.decode())["ts_emitted"]))
                except Exception:  # noqa: BLE001 — garbage is replayed byte-exact
                    datagram = bytes(line)
                    passthrough += 1
                if ts is not None and prev_ts is not None and config.realtime_factor > 0:
                    delay = (ts - prev_ts).total_seconds() / config.realtime_factor
                    if delay > 0:
                        time.sleep(delay)
                prev_ts = ts or prev_ts
                sock.sendto(datagram, (config.target_host, config.target_port))
                sent += 1
    finally:
        sock.close()
    print(f"  emitted {sent} datagrams ({passthrough} raw passthrough) -> "
          f"{config.target_host}:{config.target_port} @ {config.realtime_factor}x")


def main() -> int:
    ap = argparse.ArgumentParser(description="replay cached decision JSONL as CoT XML over UDP")
    ap.add_argument("--source", type=Path, default=ROOT / "fixtures" / "smoke_25.jsonl")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4242)
    ap.add_argument("--speed", type=float, default=8.0, metavar="X",
                    help="realtime multiplier (8.0 = mission time compressed 8x)")
    args = ap.parse_args()
    run(EmitterConfig(source_jsonl=args.source, target_host=args.host,
                      target_port=args.port, realtime_factor=args.speed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
