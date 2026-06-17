# THESEUS — Compute Tiers & Target Platforms
*Jun 17 2026. Founder direction: target is big surface combatants (DDG/CG) with real onboard compute. The ship is its own data center + sensor mesh — not a compute-starved edge. This reframes (and strengthens) the architecture.*

## Target platforms
**DDG** (Arleigh Burke destroyers) and **CG** (Ticonderoga cruisers) — large surface combatants with real power, cooling, and rack space. Theseus is **not** SWaP-starved on these hulls. Small craft / UxV are a later, more-constrained variant.

## Two-tier onboard compute (both tiers are ON the ship)
| Tier | What it is | Runs | Hardware (real) | Dev/emulation |
|---|---|---|---|---|
| **Tier 1 — Ship central compute** | the ship's "data center" / the brain | fusion + correlation, the **anomaly/PoL models**, the **LLM explainer (Triton-TRT-LLM, GPU)**, **MLflow** registry, **retraining onboard**, the tamper-evident record | GPU-class server(s) in a ship compartment | **NVIDIA Blackwell cloud box** (emulates the ship's central compute) |
| **Tier 2 — System-component nodes** | the distributed sensing/subsystem layer (the "organs") | per-subsystem tap, **lightweight local detection** (ONNX / small GGUF), publish to Tier 1 over the ship LAN | **2× Raspberry Pi 5 (4GB)** — the real hardware we have | 2 Pis on a switch |

**Demo hardware mapping (real):** we have **2× Pi 5, 4GB** → **2 organs**: **Pi-1 = MACHINERY** (runs `update_model.py` serving the CBM gas-turbine model) · **Pi-2 = CONTACTS** (runs `ais_pol.py`, the AIS Pattern-of-Life). 4GB ⇒ small models only on the edge (CBM is tiny ✓, AIS PoL is light Python ✓, GGUF ≤~1.5B Q4 if an edge LLM is needed). A real DDG/CG scales this to more organ-nodes; the 2-Pi demo proves the pattern. Heavy reasoning stays on Tier-1 (Blackwell).

The **Pi cluster is a SUBSET** — the edge sensing layer, not the whole brain. The brain is Tier 1 (ship GPU). Tier 2 feeds Tier 1; Tier 1 reasons, recommends, and seals the record.

## Why this is a stronger story
- **GPU inference runs ON the ship**, not just ashore. The ship keeps **full reasoning** (a real explainer LLM + real PoL/anomaly models) when cut off from shore — not just tiny edge models. This makes "the ship keeps thinking when the link is cut" literally true at full capability.
- **Onboard retraining is viable** (Tier 1 GPU) — objective #3 ("live update via training at the edge") happens on the ship, not only ashore.
- The **DDIL story sharpens:** disconnected from SHORE is the *normal* condition and the ship loses nothing (its brain is aboard). Within the ship, Tier 2 components degrade gracefully (CRDT/Zenoh mesh) if a node or link drops, and Tier 1 keeps the fused picture.

## Corrects the earlier inference framing
Earlier note said "edge = GGUF only, GPU only ashore." Refined: **GPU (Triton-TRT-LLM) is the SHIP Tier-1 engine** (emulated by Blackwell); **GGUF/llama.cpp is for the Tier-2 Pi components** (local, lightweight, no GPU). vLLM Iron Bank is still out (archived); Triton-TRT-LLM on the `iron-bank` flavor is the Tier-1 path. See `../integration/INFERENCE_AND_FIPS.md`.

## Demo & dev topology (Warhacker + ongoing)
```
   SHORE (disconnected in the demo)            THE SHIP (DDG/CG)
   ───────────────────────────                ─────────────────────────────────────────
                                              Tier 1 — central compute  ← Blackwell cloud (emulated)
                                                • MLflow registry + retrain (GPU)
        (no link during                         • LLM explainer (Triton-TRT-LLM)
         the DDIL beat)                          • fusion + anomaly/PoL models
                                                • tamper-evident record
                                                      ▲           ▲
                                                      │ ship LAN (Zenoh/CRDT)
                                              Tier 2 — system components ← real Raspberry Pis
                                                PWR · PROP · NAV · DC · RDY
                                                (local detection, telemetry tap)
```
- **Blackwell cloud = Tier 1** (the ship's central GPU compute) for dev + the emulated demo.
- **Real Pis = Tier 2** (the shipboard system components).
- The model-delivery loop (`demo/`) runs across both: stage/retrain on Tier 1 (GPU), `update_model` promotes to Tier 2 nodes, every step sealed. The DDIL beat = cut shore, the whole ship brain keeps running.

## What this changes in the build
- **Tier 1 stack** (next build): the loop's retrain + the explainer containerized for GPU, deployable to the Blackwell box (Triton-TRT-LLM image, `iron-bank` flavor). *Ready to deploy when Blackwell access is provided.*
- **Tier 2 stack:** the existing `demo/update_model.py` + the AIS PoL detector run on the Pis as components (CPU/ONNX/GGUF), publishing to Tier 1.
- **UDS bundle** packages both tiers (the `deploy/` tree, in progress).

## Honest caveats
- Real DDG/CG onboard GPU depends on the program/install and must be MIL-STD ruggedized; **Blackwell emulates the capability, not the exact hardened hardware** — say so.
- Combat-system data stays **air-gapped/classified** (SWAN-side only in v1) regardless of compute.
- "Big compute aboard" is the DDG/CG case; the constrained-edge (Pi-only) variant still matters for small platforms later.
