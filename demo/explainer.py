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


def main() -> int:
    ap = argparse.ArgumentParser(description="Explainable-alert layer over deterministic detections.")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--model", default="qwen2.5:1.5b")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    a = ap.parse_args()

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
    for ev in events:
        facts = (f"event_type={ev.get('type')}; vessel_class={ev.get('vessel_class')}; "
                 f"mmsi={ev.get('mmsi')}; confidence={ev.get('confidence')}; evidence=\"{ev.get('why')}\"")
        if use_llm:
            try:
                parsed = _parse(_llm(a.base_url, a.model, facts))
                source = a.model
                llm_ok += 1
            except Exception as e:
                parsed = {"alert": ev.get("why", ""), "action": ev.get("recommended_action", "")}
                source = f"template (LLM error: {str(e)[:50]})"
        else:
            parsed = {"alert": ev.get("why", ""), "action": ev.get("recommended_action", "")}
            source = "template"

        seal(RECORD, "explained_alert", f"{ev.get('type')}:{ev.get('mmsi')}",
             {"mmsi": ev.get("mmsi"), "type": ev.get("type"), "confidence": ev.get("confidence"),
              "alert": parsed["alert"], "action": parsed["action"], "explainer": source,
              "grounded_in": ev.get("why")})
        print(f"\n  ⚠ [{ev.get('type')} · {ev.get('vessel_class')} · MMSI {ev.get('mmsi')}]")
        print(f"    ALERT : {parsed['alert']}")
        print(f"    ACTION: {parsed['action']}")
    print(f"\n  sealed {len(events)} explained alerts ({llm_ok} via {a.model}, {len(events)-llm_ok} via template) — human-in-command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
