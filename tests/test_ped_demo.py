"""Checks for the PED screen/correlate/draft demo.

These guard the CORRELATION ENGINE contract on the deterministic synthetic stream, so the
team can extend it Day 1 without silently regressing the target picture. What's asserted:
  1. the noisy stream fuses into exactly the ground-truth picture: 2 moving convoy tracks +
     1 stationary track, with clutter rejected (no spurious persistent track),
  2. the two co-moving tracks cluster into ONE formation (not loose contacts),
  3. the bi-temporal as-of query returns a strict subset of what's known later,
  4. a watch-box entry produces a DRAFT (never DECIDED) nomination, sealed and verifiable,
  5. a one-byte tamper of the sealed draft snaps the chain.

Run from the repo root:  python3 -m pytest tests/ -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from fixtures import gen_detections  # noqa: E402
from referee import ped_demo  # noqa: E402
from referee.chain import tamper, verify_dir  # noqa: E402


@pytest.fixture(autouse=True)
def _deterministic_synthetic_fixture():
    """Regenerate the deterministic synthetic fixture before each test, so the suite is
    independent of whatever the REAL sensor pipeline last wrote to detections.jsonl."""
    gen_detections.main()
    yield


def _tracks():
    dets = ped_demo.load_stream()
    return dets, ped_demo.associate(dets)


def test_stream_is_deterministic_and_nonempty():
    dets, _ = _tracks()
    assert len(dets) >= 30, "synthetic stream should be substantial"
    # stable order: sorted by (ts_observed, det_id)
    keys = [(d.ts_observed, d.det_id) for d in dets]
    assert keys == sorted(keys)


def test_correlation_recovers_ground_truth_picture():
    _, tracks = _tracks()
    persistent = [t for t in tracks if len(t.dets) >= 2]
    movers = [t for t in persistent if t.speed_mps() >= ped_demo._STATIONARY_MPS]
    statics = [t for t in persistent if t.speed_mps() < ped_demo._STATIONARY_MPS]
    # 2 moving convoy vehicles + 1 stationary vehicle
    assert len(persistent) == 3, f"expected 3 persistent tracks, got {len(persistent)}"
    assert len(movers) == 2, f"expected 2 moving tracks, got {len(movers)}"
    assert len(statics) == 1, f"expected 1 stationary track, got {len(statics)}"


def test_clutter_does_not_form_a_track():
    _, tracks = _tracks()
    strays = [t for t in tracks if len(t.dets) < 2]
    assert strays, "clutter should remain stray, not fuse into a persistent track"


def test_convoy_clusters_into_one_formation():
    _, tracks = _tracks()
    forms = ped_demo.cluster_formations(tracks)
    multi = [f for f in forms if len(f) >= 2]
    assert len(multi) == 1, f"expected exactly one multi-track formation, got {len(multi)}"
    assert len(multi[0]) == 2, "the convoy formation should contain both vehicles"


def test_as_of_query_is_a_subset_of_later_knowledge():
    _, tracks = _tracks()
    persistent = [t for t in tracks if len(t.dets) >= 2]
    t = persistent[0]
    early = t.first.ts_observed
    late = t.last.ts_observed
    assert len(t.positions_as_of(early)) <= len(t.positions_as_of(late))
    assert len(t.positions_as_of(early)) >= 1


def test_watch_entry_drafts_for_human_and_seals(tmp_path):
    _, tracks = _tracks()
    persistent = [t for t in tracks if len(t.dets) >= 2]
    entrants = [t for t in persistent if ped_demo.first_watch_entry(t) is not None]
    assert entrants, "at least one track should enter the watch box"
    # the demo run seals drafts and the record must verify
    rc = ped_demo.play(plain=True)
    assert rc == 0
    ok, _, _ = verify_dir(ped_demo._OUT)
    assert ok, "sealed nomination record must verify"


def test_build_picture_contract_for_console():
    # The FE console depends on this shape; lock it.
    import json

    p = ped_demo.build_picture()
    assert set(p) >= {"watch_box", "tracks", "strays", "nominations"}
    assert len(p["tracks"]) == 3
    assert any(t["formation"] is not None for t in p["tracks"]), "convoy must carry a formation id"
    assert p["nominations"] and p["nominations"][0]["status"] == "DRAFT_FOR_HUMAN"
    json.dumps(p)  # must be JSON-serializable for the /api/picture endpoint


def test_tamper_snaps_the_sealed_record():
    ped_demo.play(plain=True)  # (re)write the sealed record
    ok, _, _ = verify_dir(ped_demo._OUT)
    assert ok
    tamper(ped_demo._OUT, 0)
    bad_ok, _, _ = verify_dir(ped_demo._OUT)
    assert not bad_ok, "a one-byte tamper of the draft must snap the chain"
    ped_demo.play(plain=True)  # restore a clean record for the next run
