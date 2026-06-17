# THESEUS × Force OS — integration seam (light proof)
*APOLLO assessment, Jun 17. The honest, low-risk integration: Force OS orchestrates Theseus's **explainer LLM** and **model-delivery lifecycle** as workloads it coordinates and seals. Standalone Theseus is always the live fallback. Force OS stays a PRIVATE substrate behind a wire protocol — never vendored into this public repo.*

## What's proven (Force OS on Blackwell)
- 44-agent fleet runs end-to-end on **self-hosted Kimi K2.7 (vLLM, OpenAI-compatible)** via force-lite **NativeRuntime** (BYOK, one config knob for any `/v1/chat/completions`). One ~105MB binary.
- **MCP gateway** (`force_dispatch_mission` / `force_ask_agent` / `force_agent_history` / `force_fleet_roster`) = the external-dispatch seam, live-verified.
- **Caveat (hold the line):** NativeRuntime is **text-streaming only — tool calls not yet wired** (v1.1). Keep the demo to text-explanation + MCP-dispatched lifecycle steps, not tool-using agents.

## The seam (wire protocols only — no code dependency)
1. **Explainer-as-Force-OS-agent (hours, proven shape):** the Tier-1 explainer endpoint (Ollama `:11434/v1` on the demo Mac, or llama.cpp on the Pi) registers as a Force OS custom OpenAI-compat provider → a Force OS `Native` "explainer" agent. Theseus calls `force_ask_agent(explainer, <event facts>)` over MCP; the grounded watch-alert comes back **through Force OS**. *(Mirrors `demo/explainer.py`'s prompt + the `_events()` facts.)*
2. **Model-delivery mission (the real value, ~1–2 days):** a Force OS agent/squadron owns "fetch staged model → validate → push to Tier-2 Pi → verify load → **seal the record**," dispatched via `force_dispatch_mission`. Entry points it calls (Theseus side, already built): `demo/update_model.py` (promote+rollback), `demo/_record.py:seal()` (the tamper-evident seal), the podman push to a Pi. This is where governed orchestration + the sealed/replayable record genuinely earns its keep (vs the current ad-hoc Python).

## What APOLLO/SEXTANT build vs what WARHACKER provides
- **WARHACKER provides (this repo, public):** the explainer endpoint contract (OpenAI-compat, the system prompt + event-facts shape — see `demo/explainer.py`), the model-delivery entry points (`update_model.py`, `_record.seal()`, the podman push command), and the fallback discipline.
- **APOLLO/SEXTANT build (private force-core lane):** the Force OS `Native` explainer agent definition + the model-delivery mission/squadron, against the contract above. Force OS ships as a **private wheel/container**, never committed here.

## IP / AGPL boundary (clean as designed — hold it)
Force OS talks to Theseus over **OpenAI-compat HTTP + MCP (JSON-RPC) + A2A** — wire protocols, not a code dependency. The public AGPL `theseus` repo never imports force-core/forceos; Force OS is the orchestrator *behind* the interface. AGPL network-copyleft does **not** reach across the wire (separate process, separate distribution). Do not import AGPL code into force-core either.

## Demo discipline (no-regret)
Build the Force OS layer in a **worktree, demo from the box**; **standalone Theseus runs underneath as the guaranteed live default the whole time.** If the Force OS layer wobbles on the floor, the standalone demo *is* the showing. Box must be up (`brev start` resume of the proven 44-on-Kimi state).

## Deferred to next-phase (do NOT over-build for the hackathon)
Fusion/anomaly organs *under* Force OS (needs A2A-carding or MCP-tool-wrapping + tool-call parity) · SurrealDB zero-infra migration (~2 eng-days; makes "one binary, zero infra" literally true — strong for the IL5/air-gap story) · native-path tool-call parity (v1.1). These ride the existing `FORCE_LITE_KIMI_GTM_PLAN` workstreams — the Theseus integration rides that roadmap, doesn't fork it.

**The headline if it lands:** *the only ship brain whose every model update is governed, sealed, and replayable — running where the cloud can't.*
