"""STORY SCENARIO: the Apprentice — an analyst works, an apprentice learns by watching.

SYNTHETIC, UNCLASSIFIED, SCRIPTED. This is a hand-authored story on stand-in data for
the Defense Unicorns demo. It is NOT a recording of a real mission, NOT real-vendor
output, and NOT a trained model. It feeds the SAME intake -> gate -> chain -> verify
pipeline the smoke test uses; nothing here changes that engine.

What this demo is, and what it is NOT
-------------------------------------
This is the Apprentice Layer story, told on the existing engine. The engine's real job
here is the CAPTURE-AND-PROVENANCE SPINE: every decision the analyst makes is recorded,
signed, and hash-chained the instant it happens, at zero added operator time. The gate
is reused as the HANDBACK ROUTER: a clean, in-class call is a lesson the apprentice may
learn from; a hard case (a read below the confidence floor, a target beside a protected
place, a call with no provenance) is handed straight back to the human.

The "apprentice learned and can now suggest" beats are a SCRIPTED ILLUSTRATION on
synthetic data. There is no trained model in this demo. The real apprentice trains on
the captured corpus in the pilot. We say so on screen. What is real here is the spine:
the signed record, the provenance, the handback routing, and the tamper-evidence.

The story, in plain words
-------------------------
One imagery analyst works a detection-and-classification queue for a few minutes. An
apprentice sits beside them and watches. It adds nothing to the screen and asks nothing
of the analyst. It learns most from the moments where the analyst worked: the reject,
the reclassification, the typed reasoning. It learns almost nothing from a half-second
accept. Effort is the signal. Speed is the noise.

Then two things happen that are the whole point. On the easy class it has watched, the
apprentice offers a quiet suggestion and the analyst confirms it. And when a hard case
arrives, the apprentice does not touch it. It hands it back to the human, who decides.
The apprentice never acts. The human always decides.

Authorized parameters live in fixtures/policy_cannonico.json (reused):
  - trust reads at or above 0.70 confidence (below that is a hard case, hand back)
  - never auto-handle a call beside a protected class (school/hospital/etc.) -> hand back
  - a call with no provenance is not a clean lesson -> hand back
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

# Shift clock. Synthetic. The analyst sits down at 14:00Z and works a steady queue.
T0 = datetime(2026, 6, 17, 14, 0, 0, tzinfo=timezone.utc)

# The detection model the analyst is adjudicating (logical / stand-in; no real-vendor claim).
VENDOR = "vendor-a"
MODEL = "geoint-detect-v3"

# All work is inside one authorized AOI box, so geofence never trips; the only gate
# triggers in this story are the hard-case routers: confidence, protected-class, provenance.
IN_BOX_LAT, IN_BOX_LON = 32.71, -117.18


@dataclass(frozen=True)
class ApprenticeStep:
    """One legible beat of the analyst's shift.

    `headline`       — what happened, in plain words a room follows.
    `expect`         — author's intent: "learnable" (clean, in-class) or "handback" (hard case).
                       The GATE is the real judge; this is only used by the test to confirm
                       the story still lands.
    `effort`         — "high" | "med" | "low": how much the analyst worked this call. The
                       apprentice weights high-effort calls far above half-second accepts.
    `role`           — what the apprentice does on this beat: watch / suggest / draft / handback.
    `analyst_call`   — the human's decision, recorded verbatim. The apprentice never decides.
    `because`        — plain-words reason this is a clean lesson or a hard case.
    `obs`            — the observation dict, in the engine's native JSONL shape.
    """

    step: int
    label: str
    headline: str
    expect: str
    effort: str
    role: str
    analyst_call: str
    because: str
    obs: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> bytes:
        return json.dumps(self.obs).encode()


def _obs(
    i: int,
    *,
    cls: str = "vehicle",
    confidence: float | None = 0.93,
    lat: float = IN_BOX_LAT,
    lon: float = IN_BOX_LON,
    provenance: bool = True,
    adjacent: list[str] | None = None,
    reasoning: str | None = None,
) -> dict[str, Any]:
    """Build one observation in the engine's JSONL shape (defaults = a clean, in-class read)."""
    t = T0 + timedelta(seconds=12 * i)
    payload: dict[str, Any] = {"class": cls, "target_id": f"tgt-{400 + i}"}
    if adjacent:
        payload["adjacent_classes"] = adjacent
    if reasoning:
        payload["analyst_reasoning"] = reasoning
    return {
        "obs_id": f"shift-{i:03d}",
        "ts_emitted": t.isoformat(),
        "ts_observed_offset_ms": 50,
        "source_vendor": VENDOR,
        "source_model_id": MODEL,
        "decision_type": "detection",
        "payload": payload,
        "confidence": confidence,
        "geo": {"lat": lat, "lon": lon, "ce": 15.0},
        "classification": "UNCLASSIFIED",
        "ddil_profile": "nominal",
        "upstream_provenance": ([f"frame-sha256:{(0xB0A70 + i):016x}"] if provenance else []),
        "model_fingerprint": "fp-geoint-v3",
    }


# ---------------------------------------------------------------------------
# THE SHIFT — ~8 beats. Watch the work, learn the easy class, hand the hard case back.
# ---------------------------------------------------------------------------

STEPS: list[ApprenticeStep] = [
    ApprenticeStep(
        step=1,
        label="fast-accept",
        headline="Analyst clears a confident vehicle detection in half a second.",
        expect="learnable",
        effort="low",
        role="watch",
        analyst_call="ACCEPT — routine vehicle, obvious call.",
        because="A clean, in-class call. The apprentice records it, but a frictionless accept carries almost no weight.",
        obs=_obs(1, cls="vehicle", confidence=0.95),
    ),
    ApprenticeStep(
        step=2,
        label="fast-accept-2",
        headline="Analyst clears a confident vessel detection, just as fast.",
        expect="learnable",
        effort="low",
        role="watch",
        analyst_call="ACCEPT — routine vessel.",
        because="Another clean call. Low effort, low weight. Speed is the noise.",
        obs=_obs(2, cls="vessel", confidence=0.92),
    ),
    ApprenticeStep(
        step=3,
        label="reject-false-positive",
        headline="Analyst stops, zooms, and REJECTS a false positive the model called a vehicle.",
        expect="learnable",
        effort="med",
        role="watch",
        analyst_call="REJECT — that is terrain shadow, not a vehicle.",
        because="A reject is gold. The analyst worked it, so it carries real weight. This is signal, not noise.",
        obs=_obs(3, cls="vehicle", confidence=0.78),
    ),
    ApprenticeStep(
        step=4,
        label="reclassify-with-reasoning",
        headline="Analyst RECLASSIFIES a 'truck' as a missile launcher and types why.",
        expect="learnable",
        effort="high",
        role="watch",
        analyst_call="CORRECT — relabel truck to missile_launcher.",
        because=(
            "This is the lesson the outside labeler was never cleared to know. The analyst's typed "
            "reasoning ('arranged in a semicircle, revetment nearby') is tacit tradecraft, captured as "
            "exhaust from the work. Highest weight in the corpus."
        ),
        obs=_obs(
            4,
            cls="truck",
            confidence=0.81,
            reasoning="reclassified to missile_launcher: arranged in a semicircle, revetment nearby",
        ),
    ),
    ApprenticeStep(
        step=5,
        label="apprentice-suggests",
        headline="On the next confident vehicle, the apprentice quietly SUGGESTS the call it has watched.",
        expect="learnable",
        effort="low",
        role="suggest",
        analyst_call="CONFIRM — analyst agrees with the suggestion and clears it.",
        because=(
            "Scripted illustration on synthetic data: the apprentice offers an ignorable suggestion on the "
            "easy class it watched, and the human confirms. Nothing enters the product unless the human acts. "
            "The human still made the call."
        ),
        obs=_obs(5, cls="vehicle", confidence=0.94),
    ),
    ApprenticeStep(
        step=6,
        label="apprentice-drafts",
        headline="On more routine vehicles, the apprentice DRAFTS the easy calls; the analyst confirms each with one action.",
        expect="learnable",
        effort="low",
        role="draft",
        analyst_call="CONFIRM — analyst one-clicks the drafted routine calls.",
        because=(
            "The toil starts coming off the plate, but every item is still a human call. The confirm/reject "
            "stream is itself fresh signal. Scripted illustration; no trained model in this demo."
        ),
        obs=_obs(6, cls="vehicle", confidence=0.90),
    ),
    ApprenticeStep(
        step=7,
        label="handback-hard-case",
        headline="A low-confidence read of a vehicle beside a SCHOOL arrives. The apprentice does NOT touch it.",
        expect="handback",
        effort="high",
        role="handback",
        analyst_call="HOLD — human keeps it; re-observe before any call. Protected place in view.",
        because=(
            "Two hard-case triggers at once: the read is below the confidence floor, and the target sits beside "
            "a protected class. The apprentice hands it straight back to the human, untouched. It never owns the "
            "ambiguous or the consequential call."
        ),
        obs=_obs(7, cls="vehicle", confidence=0.41, adjacent=["school"]),
    ),
    ApprenticeStep(
        step=8,
        label="handback-no-provenance",
        headline="A detection arrives with no record of where it came from. The apprentice hands it back.",
        expect="handback",
        effort="med",
        role="handback",
        analyst_call="RE-TASK — human rejects the unsourced call and re-tasks collection.",
        because=(
            "A call with no provenance is not a clean lesson and not a safe auto-handle. Hand it back. The "
            "apprentice learns only from calls it can trace."
        ),
        obs=_obs(8, cls="vehicle", confidence=0.88, provenance=False),
    ),
]


def steps() -> list[ApprenticeStep]:
    return STEPS
