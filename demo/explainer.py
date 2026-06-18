#!/usr/bin/env python3
"""THESEUS — explainable-alert layer (NV063 "explainable AI alerting").

Takes a DETERMINISTIC detection (from ais_pol / the models, sealed in the record) and asks a
small local LLM — qwen2.5:1.5b, the same model the team runs on the Pis — to write a concise
watch-station alert + recommended action, grounded ONLY in the evidence. The LLM is a
NARRATOR over deterministic findings: it never invents positions/identities/causes, never
decides, never acts. Decision-support, human-in-command. Each explained alert is sealed.

Runs against any OpenAI-compatible endpoint (Ollama :11434 here = Tier-1; the Pi's llama.cpp
server in the field). Falls back to the deterministic template if no LLM is reachable.

  python3 demo/explainer.py [--n 5] [--model qwen2.5:1.5b] [--base-url http://127.0.0.1:11434/v1]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.request
from pathlib import Path

from _record import seal

HERE = Path(__file__).resolve().parent
RECORD = HERE / "out" / "record"

SYSTEM = (
    "You are THESEUS, a U.S. Navy watch-station decision-support assistant on a ship operating "
    "under degraded comms. You are given ONE detected event with its evidence. Write a single "
    "concise watch alert (one sentence) and a recommended action (one sentence) for the watch "
    "officer. Use ONLY the facts provided — never invent positions, identities, intent, or causes. "
    "You recommend; the watch officer decides and acts. Reply as compact JSON: "
    '{"alert": "...", "action": "..."}'
)


def _llm(base_url: str, model: str, user: str, timeout: int = 60) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 0.2,
        "stream": False,
    }).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def _parse(text: str) -> dict:
    """Pull {alert, action} out of the model's reply (tolerant of fences/prose)."""
    try:
        s = text[text.index("{"): text.rindex("}") + 1]
        d = json.loads(s)
        return {"alert": str(d.get("alert", "")).strip(), "action": str(d.get("action", "")).strip()}
    except Exception:
        return {"alert": text.strip()[:240], "action": ""}


# ───────────────────────── deterministic grounding gate ─────────────────────────
#
# The LLM is a NARRATOR over deterministic findings, but nothing yet *enforces* that.
# A small local model can — and the THESEUS team has observed it do exactly this —
# invent a ship NAME (the facts carry only an MMSI number, never a name), restate the
# wrong event type, or fabricate a position/cause. If that ungrounded text is sealed,
# the tamper-evident record makes a hallucination look cryptographically trustworthy.
#
# This gate sits BETWEEN the LLM parse and the seal. It is fully deterministic — pure
# string/set/regex logic, no LLM, no network — so an offline zero-trust verifier can
# replay it. It enforces the 2026 grounding pattern (entity cross-referencing + schema-
# constrained extractive faithfulness): the alert may only speak about entities that are
# in the structured detection facts, and must not contradict them. It catches the
# "fabrication of entities" failure mode head-on: any capitalized proper-noun token that
# is not a known maritime/THESEUS term and is not present in the facts is a hallucinated
# entity → the gate REFUSES to seal the LLM text as model-grounded and falls back LOUDLY
# to the deterministic template (which is grounded by construction).

# Domain vocabulary the narrator is allowed to use without it counting as an invented
# entity: detection types, vessel classes, sensors/agencies, and watch-station verbs.
# Anything capitalized OUTSIDE this set (and not derived from the facts) is treated as a
# fabricated named entity (e.g. a ship name like "Sea Dragon" or a port like "Shanghai").
_GROUNDING_VOCAB = {
    # event types (ais_pol.detect) + their natural-language surface forms
    "loiter", "loitering", "overspeed", "dark", "gap", "dark-gap", "darkgap",
    "position", "jump", "position-jump", "spoof", "spoofing", "gnss", "ais",
    # vessel classes (ais_pol._bucket)
    "cargo", "tanker", "passenger", "fishing", "other", "vessel", "ship", "track",
    "contact", "mmsi",
    # watch-station / decision-support framing words the narrator may use
    "theseus", "navy", "watch", "officer", "sensor", "sensors", "verify", "flag",
    "intent", "rendezvous", "surveillance", "transit", "transited", "anomalous",
    "underway", "anchor", "knots", "kn", "nm", "min", "hours", "h", "sog",
    "recommend", "recommended", "action", "alert", "possible", "identity", "swap",
    "behavior", "behaviour", "quality", "cue", "another", "near", "zero",
    # generic sentence-initial / connective words that get capitalized
    "a", "an", "the", "this", "that", "vessel's", "ship's", "while", "no", "if",
}

# A token is "name-like" (a candidate invented entity) if it is alphabetic, starts with a
# capital, and is not ALL-CAPS (ALL-CAPS short tokens are usually acronyms like AIS/GNSS/SOG,
# already in vocab). We strip trailing possessive/punct before checking.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _facts_token_set(ev: dict) -> set[str]:
    """Every lowercase word that legitimately appears in the structured detection facts.
    The grounded narrator may reuse any of these; anything else name-like is invented."""
    toks: set[str] = set()
    for key in ("type", "vessel_class", "why", "recommended_action"):
        val = ev.get(key)
        if val is None:
            continue
        for w in _WORD_RE.findall(str(val).lower()):
            toks.add(w)
    # the MMSI is the ONLY identity in the facts; allow its digits to appear verbatim
    if ev.get("mmsi") is not None:
        toks.add(str(ev["mmsi"]).lower())
    return toks


def ground_alert(ev: dict, parsed: dict) -> tuple[bool, str]:
    """Deterministic grounding gate. Returns (grounded, reason).

    grounded=True  ⇒ the LLM text invents no entity outside the structured facts AND is
                     consistent with them; it is safe to seal as model-grounded.
    grounded=False ⇒ a specific violation (named in `reason`); the caller MUST fall back
                     to the deterministic template and seal source=template.

    Checks (all deterministic, replayable offline):
      1. NON-EMPTY    — an empty alert is not a grounded explanation.
      2. NO INVENTED ENTITY — no capitalized proper-noun token in alert/action that is not
                        in the facts and not in the allowed domain vocabulary (catches the
                        known ship-name hallucination, ports, call signs, fabricated agencies).
      3. NO FOREIGN MMSI / IDENTIFIER — any 7+ digit run (an MMSI/IMO/MID) must equal the
                        detection's own MMSI; a different number is an invented identity.
      4. CONSISTENT CLASS — if the alert names a vessel class, it must be the detected one
                        (calling a tanker a "fishing vessel" misrepresents the source).
    """
    alert = (parsed.get("alert") or "").strip()
    action = (parsed.get("action") or "").strip()
    if not alert:
        return False, "empty alert"

    text = f"{alert} {action}"
    facts = _facts_token_set(ev)

    # 2 — invented named entities (the ship-name hallucination)
    for tok in _WORD_RE.findall(text):
        low = tok.strip("'-").lower()
        if not low:
            continue
        if not tok[0].isupper():
            continue            # not name-like
        if tok.isupper():
            continue            # acronym (AIS, GNSS, SOG, MMSI) — handled by vocab anyway
        if low in _GROUNDING_VOCAB or low in facts:
            continue            # allowed domain word or a word straight from the facts
        return False, f"invented entity not in detection facts: {tok!r}"

    # 3 — foreign identifiers (a different MMSI/IMO = a fabricated identity)
    own = str(ev.get("mmsi") or "")
    for num in re.findall(r"\d{7,}", text):
        if num != own:
            return False, f"invented identifier {num!r} != detection MMSI {own!r}"

    # 4 — vessel-class consistency (don't relabel a tanker as fishing)
    detected_class = str(ev.get("vessel_class") or "").lower()
    classes = {"cargo", "tanker", "passenger", "fishing"}
    mentioned = {w for w in (_WORD_RE.findall(text.lower())) if w in classes}
    if mentioned and detected_class in classes and detected_class not in mentioned:
        return False, (f"class mismatch: alert says {sorted(mentioned)} "
                       f"but detection is {detected_class!r}")

    return True, "grounded in detection facts"


def _events(n: int) -> list[dict]:
    cp = RECORD / "chain.jsonl"
    if not cp.exists():
        return []
    out = []
    for line in cp.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "ais_anomaly":
            try:
                out.append(json.loads(base64.b64decode(row["record_b64"])))
            except Exception:
                pass
    out.sort(key=lambda e: e.get("confidence", 0), reverse=True)
    seen, uniq = set(), []   # one alert per distinct track (MMSI)
    for e in out:
        m = e.get("mmsi")
        if m in seen:
            continue
        seen.add(m)
        uniq.append(e)
    return uniq[:n]


def _selftest() -> int:
    """FLEX (no LLM, no network): prove the grounding gate (a) passes a faithful alert,
    (b) CATCHES a ship-name hallucination and refuses to seal it as model-grounded, and
    (c) the gated leaf is sealed with explainer=template + grounded=False provenance, in
    an ISOLATED temporary record dir (never touches demo/out or the live record)."""
    import tempfile
    global RECORD

    # a real detection fact set, exactly as ais_pol seals it (no ship name — only an MMSI).
    ev = {"mmsi": "338901234", "type": "loiter", "vessel_class": "cargo", "confidence": 0.7,
          "why": "transited then loitered: 24/30 fixes <0.5kn over 3.1h (peak 14kn)",
          "recommended_action": "verify intent; flag for watch — possible surveillance/rendezvous"}

    # GOOD: faithful narration, reuses only words/identity from the facts → grounded.
    ok, why = ground_alert(ev, {
        "alert": "Cargo track MMSI 338901234 transited then loitered near zero knots for 3.1h.",
        "action": "Verify intent and flag for watch — possible surveillance or rendezvous."})
    assert ok, f"faithful alert wrongly blocked: {why}"

    # HALLUCINATION 1: invents a ship NAME ('Sea Dragon') that is in NO fact → must block.
    ok, why = ground_alert(ev, {
        "alert": "Cargo vessel Sea Dragon loitered suspiciously near the strait.",
        "action": "Verify intent."})
    assert not ok, "ship-name hallucination was NOT caught"
    assert "invented entity" in why, why
    print(f"  ✓ gate caught invented ship name: {why}")

    # HALLUCINATION 2: invents a foreign MMSI (a fabricated identity) → must block.
    ok, why = ground_alert(ev, {
        "alert": "Track MMSI 999888777 loitered near zero knots.", "action": "Verify."})
    assert not ok and "invented identifier" in why, f"foreign MMSI not caught: {why}"
    print(f"  ✓ gate caught foreign identifier: {why}")

    # HALLUCINATION 3: relabels the vessel class (tanker→fishing) → must block.
    ok, why = ground_alert({**ev, "vessel_class": "tanker"}, {
        "alert": "Fishing vessel loitered near zero knots.", "action": "Verify."})
    assert not ok and "class mismatch" in why, f"class mismatch not caught: {why}"
    print(f"  ✓ gate caught vessel-class mismatch: {why}")

    # PROVENANCE: a gated alert must seal as explainer=template + grounded=False, and the
    # record must still verify PASS (the gate degrades safely, it never breaks the chain).
    with tempfile.TemporaryDirectory() as td:
        RECORD = Path(td) / "record"
        bad = {"alert": "Cargo vessel Sea Dragon loitered.", "action": "Verify."}
        ok, reason = ground_alert(ev, bad)
        assert not ok
        parsed = {"alert": ev["why"], "action": ev["recommended_action"]}  # template fallback
        seal(RECORD, "explained_alert", f"{ev['type']}:{ev['mmsi']}",
             {"mmsi": ev["mmsi"], "type": ev["type"], "confidence": ev["confidence"],
              "alert": parsed["alert"], "action": parsed["action"],
              "explainer": f"template (grounding gate: {reason})", "grounded": False,
              "grounded_in": ev["why"]})
        row = json.loads((RECORD / "chain.jsonl").read_text().splitlines()[-1])
        sealed = json.loads(base64.b64decode(row["record_b64"]))
        assert sealed["grounded"] is False, "gated leaf not marked grounded=False"
        assert sealed["explainer"].startswith("template"), "gated leaf not sealed as template"
        assert "Sea Dragon" not in json.dumps(sealed), "hallucinated text leaked into the seal"
        from referee.chain import verify_dir
        vok, _, msg = verify_dir(RECORD)
        assert vok, f"record did not verify after gated seal: {msg}"
        print(f"  ✓ hallucination sealed as template/grounded=False; record verifies: {msg}")

    print("\n  GROUNDING GATE self-test PASSED — hallucination caught, refused as model-grounded.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Explainable-alert layer over deterministic detections.")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--model", default="qwen2.5:1.5b")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--selftest", action="store_true",
                    help="run the deterministic grounding-gate self-test (no LLM, no network)")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    events = _events(a.n)
    if not events:
        print("  no ais_anomaly events in the record — run demo/ais_pol.py first")
        return 1
    print(f"THESEUS · explainable-alert layer  (model: {a.model})")

    # is the LLM reachable?
    use_llm = True
    try:
        urllib.request.urlopen(a.base_url.rstrip("/") + "/models", timeout=5).read()
    except Exception as e:
        use_llm = False
        print(f"  (no LLM at {a.base_url} — {e}; using deterministic template fallback)")

    llm_ok = 0
    gated = 0
    for ev in events:
        facts = (f"event_type={ev.get('type')}; vessel_class={ev.get('vessel_class')}; "
                 f"mmsi={ev.get('mmsi')}; confidence={ev.get('confidence')}; evidence=\"{ev.get('why')}\"")
        template = {"alert": ev.get("why", ""), "action": ev.get("recommended_action", "")}
        grounded = True
        if use_llm:
            try:
                parsed = _parse(_llm(a.base_url, a.model, facts))
                source = a.model
                # DETERMINISTIC GROUNDING GATE — between the LLM parse and the seal.
                # If the LLM invented an entity or contradicts the detection, REFUSE to seal
                # it as model-grounded and fall back LOUDLY to the template.
                ok, reason = ground_alert(ev, parsed)
                if ok:
                    llm_ok += 1
                else:
                    print(f"  ⚠ GROUNDING GATE blocked {a.model} on MMSI {ev.get('mmsi')}: "
                          f"{reason} — falling back to template (NOT sealed as model-grounded)")
                    parsed = template
                    source = f"template (grounding gate: {reason})"
                    grounded = False
                    gated += 1
            except Exception as e:
                parsed = template
                source = f"template (LLM error: {str(e)[:50]})"
        else:
            parsed = template
            source = "template"

        seal(RECORD, "explained_alert", f"{ev.get('type')}:{ev.get('mmsi')}",
             {"mmsi": ev.get("mmsi"), "type": ev.get("type"), "confidence": ev.get("confidence"),
              "alert": parsed["alert"], "action": parsed["action"], "explainer": source,
              "grounded": grounded, "grounded_in": ev.get("why")})
        print(f"\n  ⚠ [{ev.get('type')} · {ev.get('vessel_class')} · MMSI {ev.get('mmsi')}]")
        print(f"    ALERT : {parsed['alert']}")
        print(f"    ACTION: {parsed['action']}")
    print(f"\n  sealed {len(events)} explained alerts ({llm_ok} via {a.model} grounded, "
          f"{gated} gated→template, {len(events)-llm_ok-gated} template-direct) — human-in-command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
