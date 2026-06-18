#!/usr/bin/env python3
"""THESEUS edge explainer — plain-language NV063 alerts generated ON the edge node.

NV063 = "explainable AI alerting". This turns a DETERMINISTIC detection (from the
models / ais_pol, already sealed in the edge's record) into a concise watch-station
alert + recommended action, written by the LOCAL small LLM on the Pi — Qwen 2.5 3B,
the model the team already runs on Pi-1 via goose. The LLM is a NARRATOR over
deterministic findings: it never invents positions/identities/causes, never decides,
never acts. Decision-support, human-in-command. Each explained alert is sealed.

Two LLM backends (auto-detected, in order); template fallback if neither is up:
  1. goose    — `goose run --text ...` against the Pi's configured local provider
                (default; this is how Pi-1 is set up). CPU/RAM-light, fully offline.
  2. openai   — any OpenAI-compatible /v1/chat/completions endpoint goose/ollama/
                llama.cpp exposes (e.g. ollama :11434). Pick with --backend openai.
  3. template — deterministic, zero-LLM fallback built straight from the evidence.
                Always works, even on a fresh Pi with no model loaded.

CPU/RAM discipline: one event at a time, short prompt, low temperature, hard timeout,
no batching, no extra deps (stdlib + the `goose` binary that is already on the Pi).

  python3 serve/explain_local.py --record-dir demo/out/record --n 3
  python3 serve/explain_local.py --backend openai --base-url http://127.0.0.1:11434/v1 --model qwen2.5:3b
  python3 serve/explain_local.py --backend template     # force the deterministic path
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "demo"))   # reuse the demo's record sealer, no copy
DEFAULT_RECORD_DIR = ROOT / "demo" / "out" / "record"

SYSTEM = (
    "You are THESEUS, a U.S. Navy watch-station decision-support assistant on a ship "
    "operating under degraded comms. You are given ONE detected event with its evidence. "
    "Write a single concise watch alert (one sentence) and a recommended action (one "
    "sentence) for the watch officer. Use ONLY the facts provided — never invent positions, "
    "identities, intent, or causes. You recommend; the watch officer decides and acts. "
    'Reply as compact JSON: {"alert": "...", "action": "..."}'
)


# ───────────────────────── backends ─────────────────────────

def _parse(text: str) -> dict:
    """Pull {alert, action} out of a model reply (tolerant of fences/prose)."""
    try:
        s = text[text.index("{"): text.rindex("}") + 1]
        d = json.loads(s)
        return {"alert": str(d.get("alert", "")).strip(),
                "action": str(d.get("action", "")).strip()}
    except Exception:
        return {"alert": text.strip()[:240], "action": ""}


def _llm_goose(model: str | None, facts: str, timeout: int) -> dict:
    """Ask the Pi's local provider via the goose CLI. goose uses its configured
    provider/model (Qwen 2.5 3B on Pi-1), so this stays fully offline.

    Headless flags: -q (model response only), --no-session (no session file written on
    the Pi), --system (system prompt), --text (the event facts). --model overrides the
    configured model when one is passed; otherwise goose's config picks it.
    """
    goose = shutil.which("goose")
    if not goose:
        raise RuntimeError("goose not on PATH")
    cmd = [goose, "run", "-q", "--no-session",
           "--system", SYSTEM,
           "--text", f"EVENT FACTS:\n{facts}\n\nReply with ONLY the JSON object."]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"goose rc={proc.returncode}: {proc.stderr.strip()[:160]}")
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError("goose returned empty output")
    return _parse(out)


def _llm_openai(base_url: str, model: str, facts: str, timeout: int) -> dict:
    """Any OpenAI-compatible endpoint (ollama/llama.cpp goose can also point at)."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": facts}],
        "temperature": 0.2,
        "stream": False,
    }).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return _parse(data["choices"][0]["message"]["content"])


def _template(ev: dict) -> dict:
    """Deterministic fallback — straight from the sealed evidence, no LLM."""
    return {"alert": ev.get("why", "") or f"{ev.get('type')} on {ev.get('vessel_class')}",
            "action": ev.get("recommended_action", "") or "Refer to watch officer."}


# ───────────────────────── deterministic grounding gate ─────────────────────────
#
# The LLM is a NARRATOR over deterministic findings, but nothing yet *enforces* that.
# A small edge model can — and has been observed to — invent a ship NAME (the facts carry
# only an MMSI number, never a name), restate the wrong event type, or fabricate a cause.
# Sealing that ungrounded text would make a hallucination look cryptographically trustworthy.
#
# This gate sits BETWEEN the LLM parse and the seal. It is fully deterministic — pure
# string/set/regex logic, no LLM, no network — so an offline zero-trust verifier can replay
# it on the edge node. It enforces the 2026 grounding pattern (entity cross-referencing +
# schema-constrained extractive faithfulness): the alert may only speak about entities present
# in the structured detection facts, and must not contradict them. On any violation the gate
# REFUSES to seal the LLM text as model-grounded and the caller falls back LOUDLY to the
# deterministic template (grounded by construction). Kept identical to demo/explainer.py so the
# Tier-1 and edge paths gate the same way.

_GROUNDING_VOCAB = {
    "loiter", "loitering", "overspeed", "dark", "gap", "dark-gap", "darkgap",
    "position", "jump", "position-jump", "spoof", "spoofing", "gnss", "ais",
    "cargo", "tanker", "passenger", "fishing", "other", "vessel", "ship", "track",
    "contact", "mmsi",
    "theseus", "navy", "watch", "officer", "sensor", "sensors", "verify", "flag",
    "intent", "rendezvous", "surveillance", "transit", "transited", "anomalous",
    "underway", "anchor", "knots", "kn", "nm", "min", "hours", "h", "sog",
    "recommend", "recommended", "action", "alert", "possible", "identity", "swap",
    "behavior", "behaviour", "quality", "cue", "another", "near", "zero",
    "a", "an", "the", "this", "that", "vessel's", "ship's", "while", "no", "if",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _facts_token_set(ev: dict) -> set[str]:
    """Every lowercase word that legitimately appears in the structured detection facts."""
    toks: set[str] = set()
    for key in ("type", "vessel_class", "why", "recommended_action"):
        val = ev.get(key)
        if val is None:
            continue
        for w in _WORD_RE.findall(str(val).lower()):
            toks.add(w)
    if ev.get("mmsi") is not None:
        toks.add(str(ev["mmsi"]).lower())
    return toks


def ground_alert(ev: dict, parsed: dict) -> tuple[bool, str]:
    """Deterministic grounding gate. Returns (grounded, reason).

    grounded=True  ⇒ the LLM text invents no entity outside the structured facts AND is
                     consistent with them; safe to seal as model-grounded.
    grounded=False ⇒ a specific violation (named in `reason`); the caller MUST fall back to
                     the deterministic template and seal source=template.

    Checks (all deterministic, replayable offline on the edge):
      1. NON-EMPTY    — an empty alert is not a grounded explanation.
      2. NO INVENTED ENTITY — no capitalized proper-noun token in alert/action that is not in
                        the facts and not in the allowed domain vocabulary (the ship-name case).
      3. NO FOREIGN IDENTIFIER — any 7+ digit run (MMSI/IMO/MID) must equal the detection's MMSI.
      4. CONSISTENT CLASS — a named vessel class must be the detected one.
    """
    alert = (parsed.get("alert") or "").strip()
    action = (parsed.get("action") or "").strip()
    if not alert:
        return False, "empty alert"

    text = f"{alert} {action}"
    facts = _facts_token_set(ev)

    for tok in _WORD_RE.findall(text):
        low = tok.strip("'-").lower()
        if not low:
            continue
        if not tok[0].isupper():
            continue
        if tok.isupper():
            continue
        if low in _GROUNDING_VOCAB or low in facts:
            continue
        return False, f"invented entity not in detection facts: {tok!r}"

    own = str(ev.get("mmsi") or "")
    for num in re.findall(r"\d{7,}", text):
        if num != own:
            return False, f"invented identifier {num!r} != detection MMSI {own!r}"

    detected_class = str(ev.get("vessel_class") or "").lower()
    classes = {"cargo", "tanker", "passenger", "fishing"}
    mentioned = {w for w in (_WORD_RE.findall(text.lower())) if w in classes}
    if mentioned and detected_class in classes and detected_class not in mentioned:
        return False, (f"class mismatch: alert says {sorted(mentioned)} "
                       f"but detection is {detected_class!r}")

    return True, "grounded in detection facts"


# ───────────────────────── events from the edge's own record ─────────────────────────

def _events(record_dir: Path, n: int) -> list[dict]:
    cp = Path(record_dir) / "chain.jsonl"
    if not cp.exists():
        return []
    out: list[dict] = []
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
    seen, uniq = set(), []   # one alert per distinct track
    for e in out:
        m = e.get("mmsi")
        if m in seen:
            continue
        seen.add(m)
        uniq.append(e)
    return uniq[:n]


def explain(record_dir: Path, n: int, backend: str, model: str | None,
            base_url: str, timeout: int, seal_alerts: bool = True) -> dict:
    events = _events(record_dir, n)
    if not events:
        return {"ok": False, "reason": "no ais_anomaly events in record", "alerts": []}

    seal = None
    if seal_alerts:
        try:
            from _record import seal as _seal  # demo/_record.py
            seal = _seal
        except Exception:
            seal = None

    # Probe the chosen backend ONCE; on failure, degrade to template for the whole run.
    chosen = backend
    if backend == "auto":
        chosen = "goose" if shutil.which("goose") else "openai"

    used_llm = 0
    gated = 0
    alerts = []
    for ev in events:
        facts = (f"event_type={ev.get('type')}; vessel_class={ev.get('vessel_class')}; "
                 f"mmsi={ev.get('mmsi')}; confidence={ev.get('confidence')}; "
                 f"evidence=\"{ev.get('why')}\"")
        source = "template"
        grounded = True
        parsed = _template(ev)
        if chosen != "template":
            try:
                if chosen == "goose":
                    llm_parsed = _llm_goose(model, facts, timeout)
                else:
                    llm_parsed = _llm_openai(base_url, model or "qwen2.5:3b", facts, timeout)
                if not llm_parsed.get("alert"):
                    parsed = _template(ev)
                    source = f"template ({chosen} empty)"
                else:
                    # DETERMINISTIC GROUNDING GATE — between the LLM parse and the seal.
                    # If the model invented an entity (e.g. a ship name) or contradicts the
                    # detection, REFUSE to seal it as model-grounded; fall back LOUDLY to template.
                    ok, reason = ground_alert(ev, llm_parsed)
                    if ok:
                        parsed = llm_parsed
                        source = f"{chosen}:{model or 'configured'}"
                        used_llm += 1
                    else:
                        parsed = _template(ev)
                        source = f"template (grounding gate: {reason})"
                        grounded = False
                        gated += 1
                        print(f"  ⚠ GROUNDING GATE blocked {chosen} on MMSI {ev.get('mmsi')}: "
                              f"{reason} — sealing template, NOT model-grounded", file=sys.stderr)
            except Exception as e:
                parsed = _template(ev)
                source = f"template ({chosen} error: {str(e)[:50]})"
                # If the very first LLM call fails, stop trying it (save CPU on the Pi).
                if used_llm == 0:
                    chosen = "template"

        rec = {"mmsi": ev.get("mmsi"), "type": ev.get("type"),
               "confidence": ev.get("confidence"), "alert": parsed["alert"],
               "action": parsed["action"], "explainer": source,
               "grounded": grounded, "grounded_in": ev.get("why")}
        if seal is not None:
            try:
                rec["leaf_hash"] = seal(record_dir, "explained_alert",
                                        f"{ev.get('type')}:{ev.get('mmsi')}", rec)
            except Exception as e:
                rec["seal_error"] = str(e)[:80]
        alerts.append(rec)

    return {"ok": True, "backend": chosen, "n": len(alerts),
            "llm": used_llm, "gated": gated, "template": len(alerts) - used_llm,
            "alerts": alerts}


def _selftest() -> int:
    """FLEX (no LLM, no network): prove the edge grounding gate (a) passes a faithful alert,
    (b) CATCHES a ship-name hallucination, (c) seals the gated alert as explainer=template +
    grounded=False in an ISOLATED temp record dir that verifies PASS (never touches demo/out)."""
    import tempfile

    ev = {"mmsi": "338901234", "type": "loiter", "vessel_class": "cargo", "confidence": 0.7,
          "why": "transited then loitered: 24/30 fixes <0.5kn over 3.1h (peak 14kn)",
          "recommended_action": "verify intent; flag for watch — possible surveillance/rendezvous"}

    ok, why = ground_alert(ev, {
        "alert": "Cargo track MMSI 338901234 transited then loitered near zero knots for 3.1h.",
        "action": "Verify intent and flag for watch — possible surveillance or rendezvous."})
    assert ok, f"faithful alert wrongly blocked: {why}"

    ok, why = ground_alert(ev, {
        "alert": "Cargo vessel Sea Dragon loitered suspiciously near the strait.",
        "action": "Verify intent."})
    assert not ok and "invented entity" in why, f"ship-name hallucination not caught: {why}"
    print(f"  ✓ gate caught invented ship name: {why}")

    ok, why = ground_alert(ev, {
        "alert": "Track MMSI 999888777 loitered near zero knots.", "action": "Verify."})
    assert not ok and "invented identifier" in why, f"foreign MMSI not caught: {why}"
    print(f"  ✓ gate caught foreign identifier: {why}")

    ok, why = ground_alert({**ev, "vessel_class": "tanker"}, {
        "alert": "Fishing vessel loitered near zero knots.", "action": "Verify."})
    assert not ok and "class mismatch" in why, f"class mismatch not caught: {why}"
    print(f"  ✓ gate caught vessel-class mismatch: {why}")

    # End-to-end through explain(): force a hallucinating "LLM" and assert the gate seals
    # the gated alert as template/grounded=False and the record verifies.
    with tempfile.TemporaryDirectory() as td:
        rec_dir = Path(td) / "record"
        from _record import seal as _seal
        # seed one ais_anomaly leaf so _events() picks it up
        _seal(rec_dir, "ais_anomaly", f"{ev['type']}:{ev['mmsi']}",
              {"mmsi": ev["mmsi"], "type": ev["type"], "vessel_class": ev["vessel_class"],
               "confidence": ev["confidence"], "why": ev["why"],
               "recommended_action": ev["recommended_action"]})
        # monkeypatch the openai backend to return a hallucinated ship name
        global _llm_openai
        orig = _llm_openai
        _llm_openai = lambda *a, **k: {"alert": "Cargo vessel Sea Dragon loitered.",
                                       "action": "Verify."}
        try:
            res = explain(rec_dir, n=1, backend="openai", model="stub",
                          base_url="http://stub/v1", timeout=1, seal_alerts=True)
        finally:
            _llm_openai = orig
        a0 = res["alerts"][0]
        assert a0["grounded"] is False, f"gated alert not grounded=False: {a0}"
        assert a0["explainer"].startswith("template"), f"gated alert not template: {a0}"
        assert "Sea Dragon" not in json.dumps(a0), "hallucinated text leaked into the sealed alert"
        assert res["gated"] == 1 and res["llm"] == 0, res
        from referee.chain import verify_dir
        vok, _, msg = verify_dir(rec_dir)
        assert vok, f"record did not verify after gated seal: {msg}"
        print(f"  ✓ end-to-end: hallucination gated→template/grounded=False; record verifies: {msg}")

    print("\n  EDGE GROUNDING GATE self-test PASSED — hallucination caught, refused as model-grounded.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="THESEUS edge explainer (NV063, local LLM via goose).")
    ap.add_argument("--record-dir", default=os.environ.get("RECORD_DIR", str(DEFAULT_RECORD_DIR)))
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--backend", choices=["auto", "goose", "openai", "template"],
                    default=os.environ.get("EXPLAIN_BACKEND", "auto"))
    ap.add_argument("--model", default=os.environ.get("EXPLAIN_MODEL"),
                    help="model id; for goose, omit to use the configured local model "
                         "(Qwen 2.5 3B on Pi-1)")
    ap.add_argument("--base-url", default=os.environ.get("EXPLAIN_BASE_URL",
                    "http://127.0.0.1:11434/v1"))
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("EXPLAIN_TIMEOUT", "60")))
    ap.add_argument("--no-seal", action="store_true", help="do not seal alerts (dry run)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--selftest", action="store_true",
                    help="run the deterministic grounding-gate self-test (no LLM, no network)")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    res = explain(Path(a.record_dir), a.n, a.backend, a.model, a.base_url, a.timeout,
                  seal_alerts=not a.no_seal)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if not res.get("ok"):
        print(f"  {res.get('reason')}")
        return 1
    print(f"THESEUS · edge explainer (NV063)  backend={res['backend']}")
    for r in res["alerts"]:
        print(f"\n  ⚠ [{r.get('type')} · MMSI {r.get('mmsi')}]  ({r['explainer']})")
        print(f"    ALERT : {r['alert']}")
        print(f"    ACTION: {r['action']}")
    print(f"\n  {res['n']} alerts ({res['llm']} via LLM grounded, {res.get('gated', 0)} "
          f"gated→template, {res['template']} total via template) — human-in-command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
