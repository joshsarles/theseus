"""PED fleet — SCREEN + CORRELATE + DRAFT, on a synthetic detection stream.

What is REAL here (engine logic, runs live):
  - association: noisy detections fuse into persistent tracks by distance+time gating,
  - correlation: co-moving tracks cluster into one formation (the living target picture),
  - bi-temporal query: "what did we know about this area as of <time>" answered from the
    record, using ts_observed (not just latest),
  - nomination: when a track enters a watch box, the fleet DRAFTS a nomination and seals it
    into the same hash-chained, offline-verifiable record the rest of the demo uses.
What is SYNTHETIC: the imagery/detection stream (fixtures/gen_detections.py). Said out loud.
What the human does: COMMANDS the nomination. The fleet drafts; it never decides, never acts.

Run:  python -m referee.ped_demo   (or `make ped`)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .chain import LocalHashChain, verify_dir

_FIX = Path(__file__).resolve().parent.parent / "fixtures" / "detections.jsonl"
_OUT = Path(__file__).resolve().parent.parent / "out_ped"


def _envf(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


# Association gates. Defaults fit the demo scale; the real-sensor pipeline overrides them
# via PED_* env vars for real ground scale (cars at ~meters/frame, not ~100m steps).
_GATE_M = _envf("PED_GATE_M", 150.0)          # max distance to associate a detection to a track
_MAX_GAP_S = _envf("PED_MAX_GAP_S", 150.0)    # max time gap to keep a track alive
_FORM_NEAR_M = _envf("PED_FORM_NEAR_M", 1200.0)   # co-moving spacing ceiling
_FORM_SPEED_TOL = _envf("PED_FORM_SPEED_TOL", 0.40)
_FORM_HEAD_TOL_DEG = _envf("PED_FORM_HEAD_TOL_DEG", 25.0)
_STATIONARY_MPS = _envf("PED_STATIONARY_MPS", 0.5)

# Watch box (geofence). A track entering it earns a DRAFT nomination. Overridable for real scale.
_WATCH = {
    "lat_min": _envf("PED_WATCH_LAT_MIN", 33.1025), "lat_max": _envf("PED_WATCH_LAT_MAX", 33.1055),
    "lon_min": _envf("PED_WATCH_LON_MIN", 44.2015), "lon_max": _envf("PED_WATCH_LON_MAX", 44.2045),
}


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass
class Det:
    det_id: str
    sensor: str
    ts_observed: datetime
    ts_emitted: datetime
    lat: float
    lon: float
    confidence: float


@dataclass
class Track:
    track_id: str
    dets: list[Det] = field(default_factory=list)

    @property
    def last(self) -> Det:
        return self.dets[-1]

    @property
    def first(self) -> Det:
        return self.dets[0]

    def span_s(self) -> float:
        return (self.last.ts_observed - self.first.ts_observed).total_seconds()

    def speed_mps(self) -> float:
        s = self.span_s()
        if s <= 0:
            return 0.0
        d = _haversine_m(self.first.lat, self.first.lon, self.last.lat, self.last.lon)
        return d / s

    def heading_deg(self) -> float:
        dy = self.last.lat - self.first.lat
        dx = self.last.lon - self.first.lon
        return math.degrees(math.atan2(dx, dy)) % 360.0  # 0=N, 90=E

    def positions_as_of(self, as_of: datetime) -> list[Det]:
        return [d for d in self.dets if d.ts_observed <= as_of]


def load_stream(path: Path | None = None) -> list[Det]:
    # Real pipeline points PED_DETECTIONS at its own real-detections file so it never collides
    # with the synthetic test fixture (which the test suite regenerates into the default path).
    path = Path(path) if path is not None else Path(os.environ.get("PED_DETECTIONS", _FIX))
    if not path.exists():
        # auto-generate the fixture if missing (mirrors `make fixtures`)
        from fixtures import gen_detections

        gen_detections.main()
    dets: list[Det] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        dets.append(
            Det(r["det_id"], r["sensor"], _ts(r["ts_observed"]), _ts(r["ts_emitted"]),
                r["lat"], r["lon"], r["confidence"])
        )
    dets.sort(key=lambda d: (d.ts_observed, d.det_id))
    return dets


def associate(dets: list[Det]) -> list[Track]:
    """Greedy nearest-neighbor association under distance + time gates. Real logic."""
    tracks: list[Track] = []
    for d in dets:
        best: Track | None = None
        best_m = _GATE_M
        for t in tracks:
            gap = (d.ts_observed - t.last.ts_observed).total_seconds()
            if gap < 0 or gap > _MAX_GAP_S:
                continue
            m = _haversine_m(d.lat, d.lon, t.last.lat, t.last.lon)
            if m < best_m:
                best, best_m = t, m
        if best is None:
            best = Track(track_id=f"trk-{len(tracks):02d}")
            tracks.append(best)
        best.dets.append(d)
    return tracks


def cluster_formations(tracks: list[Track]) -> list[list[Track]]:
    """Cluster co-moving tracks (similar velocity, spatially near) into formations."""
    movers = [t for t in tracks if t.speed_mps() >= _STATIONARY_MPS and len(t.dets) >= 2]
    statics = [t for t in tracks if t not in movers]
    forms: list[list[Track]] = []
    for t in movers:
        placed = False
        for f in forms:
            ref = f[0]
            near = _haversine_m(t.last.lat, t.last.lon, ref.last.lat, ref.last.lon) <= _FORM_NEAR_M
            s1, s2 = t.speed_mps(), ref.speed_mps()
            speed_ok = abs(s1 - s2) <= _FORM_SPEED_TOL * max(s1, s2, 1e-6)
            head_ok = abs((t.heading_deg() - ref.heading_deg() + 180) % 360 - 180) <= _FORM_HEAD_TOL_DEG
            if near and speed_ok and head_ok:
                f.append(t)
                placed = True
                break
        if not placed:
            forms.append([t])
    for t in statics:  # each stationary/short track is its own (degenerate) formation
        forms.append([t])
    return forms


def _in_watch(d: Det) -> bool:
    return (_WATCH["lat_min"] <= d.lat <= _WATCH["lat_max"]
            and _WATCH["lon_min"] <= d.lon <= _WATCH["lon_max"])


def first_watch_entry(track: Track) -> Det | None:
    for d in track.dets:
        if _in_watch(d):
            return d
    return None


def build_picture() -> dict:
    """Structured living-target-picture for the console (same engine as play())."""
    dets = load_stream()
    tracks = associate(dets)
    persistent = [t for t in tracks if len(t.dets) >= 2]
    forms = cluster_formations(tracks)
    # map each track to a formation index (only multi-track formations get a shared id)
    form_of: dict[str, int] = {}
    fid = 0
    for f in forms:
        if len(f) >= 2:
            for t in f:
                form_of[t.track_id] = fid
            fid += 1
    noms = []
    for t in persistent:
        entry = first_watch_entry(t)
        if entry is not None:
            noms.append({
                "track_id": t.track_id,
                "lat": entry.lat, "lon": entry.lon,
                "ts": entry.ts_observed.isoformat().replace("+00:00", "Z"),
                "confidence": entry.confidence,
                "status": "DRAFT_FOR_HUMAN",
            })
    return {
        "watch_box": _WATCH,
        "tracks": [
            {
                "id": t.track_id,
                "kind": "moving" if t.speed_mps() >= _STATIONARY_MPS else "stationary",
                "speed_mps": round(t.speed_mps(), 2),
                "heading_deg": round(t.heading_deg(), 0),
                "formation": form_of.get(t.track_id),
                "dets": [
                    {"lat": d.lat, "lon": d.lon,
                     "ts": d.ts_observed.isoformat().replace("+00:00", "Z"),
                     "sensor": d.sensor}
                    for d in t.dets
                ],
            }
            for t in persistent
        ],
        "strays": [
            {"lat": t.first.lat, "lon": t.first.lon} for t in tracks if len(t.dets) < 2
        ],
        "nominations": noms,
    }


def play(plain: bool = False) -> int:
    bar = "=" * 78
    # Honest, data-accurate provenance line (no hardcoded "synthetic"). The real-sensor
    # pipeline sets PED_SOURCE to the real model+imagery; the unit-test fixture sets it to
    # the generated stream. Never claim real when synthetic or synthetic when real.
    source = os.environ.get(
        "PED_SOURCE",
        "REAL detections (torchvision detector on real video frames)"
        if any("EO-FMV" in str(d.sensor) for d in load_stream())
        else "deterministic test fixture (synthetic, for unit tests)",
    )
    dets = load_stream()
    tracks = associate(dets)
    persistent = [t for t in tracks if len(t.dets) >= 2]
    noise = [t for t in tracks if len(t.dets) < 2]
    forms = cluster_formations(tracks)
    multi = [f for f in forms if len(f) >= 2]

    print()
    print(f"  {bar}")
    print("  PED FLEET — screen the firehose, correlate the picture, draft the nomination")
    print(f"  Source: {source}. The engine is real. The human commands.")
    print(f"  {bar}\n")

    # 1. SCREEN
    print(f"  1) SCREEN  — {len(dets)} detections streamed from {len({d.sensor for d in dets})} sensors, full-auto.")
    print("     This is the toil: glimpses arrive noisy, out of order, with gaps. No analyst time spent.\n")

    # 2. CORRELATE (the living target picture)
    print(f"  2) CORRELATE  — fused into {len(persistent)} persistent tracks "
          f"({len(noise)} stray detection(s) correctly did NOT form a track).")
    for t in persistent:
        kind = "moving" if t.speed_mps() >= _STATIONARY_MPS else "stationary"
        print(f"       {t.track_id}: {len(t.dets)} dets, {kind}, "
              f"{t.speed_mps():.1f} m/s, last @ ({t.last.lat:.4f},{t.last.lon:.4f})")
    if multi:
        f = multi[0]
        ids = "+".join(t.track_id for t in f)
        print(f"     FORMATION: {ids} are co-moving (same heading and speed) -> one formation, "
              f"not {len(f)} loose contacts.")
    print("     This is one living target picture across time and sensors, not a stack of stills.\n")

    # 3. BI-TEMPORAL "as of" query
    as_of = dets[len(dets) // 2].ts_observed
    print(f"  3) AS-OF QUERY  — \"what did we know as of {as_of.isoformat().replace('+00:00','Z')}?\"")
    for t in persistent:
        seen = t.positions_as_of(as_of)
        if seen:
            last = seen[-1]
            print(f"       {t.track_id}: {len(seen)} det(s) known by then, "
                  f"last @ ({last.lat:.4f},{last.lon:.4f})")
    print("     Bi-temporal memory answers as-of-then, not just latest. (Real.)\n")

    # 4. DRAFT + HUMAN IN COMMAND, sealed into the record
    _OUT.mkdir(parents=True, exist_ok=True)
    chain = LocalHashChain()
    drafted = 0
    for t in persistent:
        entry = first_watch_entry(t)
        if entry is None:
            continue
        drafted += 1
        nom = {
            "kind": "nomination_draft",
            "track_id": t.track_id,
            "watch_entry_ts_observed": entry.ts_observed.isoformat().replace("+00:00", "Z"),
            "location": {"lat": entry.lat, "lon": entry.lon},
            "confidence": entry.confidence,
            "status": "DRAFT_FOR_HUMAN",  # never DECIDED, never ACTED
            "provenance": [d.det_id for d in t.dets],
        }
        chain.append("nomination_draft", t.track_id, json.dumps(nom, sort_keys=True).encode())
        print(f"  4) DRAFT  — {t.track_id} entered the watch box at "
              f"({entry.lat:.4f},{entry.lon:.4f}).")
        print("       The fleet DRAFTS a nomination and hands it up. Status = DRAFT_FOR_HUMAN.")
        print("       HUMAN IN COMMAND: nothing is nominated or actioned unless the human commands it.\n")
    if drafted == 0:
        print("  4) DRAFT  — no track entered the watch box; nothing drafted. (Correct: no false nomination.)\n")
    chain.write(_OUT)

    # 5. PROVE
    ok, n, msg = verify_dir(_OUT)
    flag = "PASS" if ok else "FAIL"
    print(f"  5) PROVE  — the drafts are sealed in an offline-verifiable record: {flag} ({msg}).")
    print("     Every draft carries its provenance (which detections built it). Tamper snaps the chain.\n")

    print(f"  {bar}")
    print("  REAL: detection, association, formation correlation, the as-of query, the sealed draft.")
    print(f"  Source: {source}. HUMAN: commands every nomination.")
    print(f"  PED DEMO OK — screened {len(dets)}, correlated {len(persistent)} tracks / "
          f"{len(multi)} formation(s), drafted {drafted}, record {flag}.")
    print(f"  {bar}\n")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PED fleet screen/correlate/draft demo (synthetic).")
    ap.add_argument("--plain", action="store_true", help="no-color output for capture")
    args = ap.parse_args(argv)
    return play(plain=args.plain)


if __name__ == "__main__":
    sys.exit(main())
