# THESEUS-on-UDS — Defense Unicorns Integration Plan
*Jun 17 2026, sourced. DU = Warhacker host + UDS platform vendor = **partner, not competitor**. Posture: ride DU's accredited airgap rails; package Theseus as a UDS mission app.*

## Why this matters (it kills 2 of our 3 kill-risks)
The Red Team's top kill-risks were **(1) no ATO sponsor / ATO is the long pole** and **(2) no path onto a hull**. Riding UDS attacks both:
- **ATO inheritance:** the **UDS Army model (Feb 2026)** deploys apps into pre-authorized gov environments that **inherit the existing authorization** — ~**18 months → ~2 weeks**, >70% doc-cost reduction, via automated DevSecOps scanning + continuous SBOM/compliance artifacts. We inherit the NIST 800-53 technical baseline; we only write the Theseus *delta* body-of-evidence.
- **Path onto a hull:** **Navy + Leidos shipboard delivery OTA (Apr 2026)** — selected by **NIWC Atlantic's Rapid Capabilities Cell** to prototype remote containerized software delivery to ships (replacing pier-side disk-loading). **🔑 Justin Hodges (on our team) is Deputy Director of that exact cell.** That's the literal rail Theseus rides onto a ship — and we have an inside relationship to it.
Plus CANES NextGen (DU joined Oct 2025), DU's **"Bubble"** ruggedized DDIL edge compute, **UDS Fleet** (Jun 2026), and the **UDS Registry** (IL6+ airgap "app store") as the discoverability on-ramp. Navy containerization is now DON policy (Jul 2025).

## What we get for FREE (inherit) vs. BUILD (our differentiation)
| FREE from UDS Core | BUILD (Theseus) |
|---|---|
| K8s + airgap delivery (Zarf), OCI registry | Local Anomaly Cell (PyTorch/ONNX models) |
| **Istio** mTLS mesh + default-deny networking | Tamper-evident **append-only record** store |
| **Keycloak + Authservice** SSO/RBAC = human-in-command authn | Distributed **LLM explainer** + edge vector store / RAG |
| **Falco** runtime security; **Loki/Vector** audit logs | Custom **Pepr policy module** (our highest-leverage differentiator — see below) |
| **Prometheus/Grafana** telemetry; **Velero** backup | Decision-support UX / edge-autonomy logic |
| **SBOM + compliance artifacts**, 800-53 baseline, ATO inheritance | The Theseus RMF delta only |
| The on-ramp to the hull (DU+Leidos OTA, CANES, Bubble) | The naval analytics that matter |

## The components
- **UDS Core (v1.0, Mar 2026):** airgap-native hardened Kubernetes — Istio (STRICT mTLS, default-deny), Keycloak+Authservice, Falco, Loki/Vector, Prometheus/Grafana/Metrics-Server, Velero, Pepr-based UDS Operator. Theseus runs as ordinary pods inside an already-hardened, already-monitored, zero-trust mesh.
- **Zarf (v0.78, Jun 2026):** airgap package manager (we already use it). Best practices: **pin every image by digest**, flatten all dependent images (PyTorch/ONNX runtime, model server, vector DB) so nothing pulls at sea, declarative components only, **ship the SBOM** (it's an ATO artifact), **cosign-sign + verify on-hull**, wrap in a **UDS Bundle** (`uds.yaml`).
- **Pepr (v1.0, Nov 2025):** TypeScript K8s admission/operator framework (the UDS Operator is built on it). **🔑 Author a custom Theseus Pepr module** that *cluster-enforces* our invariants: explainer pod **no egress**, anomaly records **append-only**, **human-in-command approval CR required before any autonomy action is admitted**. This turns our rails into machine-enforced controls = the strongest safety-case artifact, lowest cost.
- **LeapfrogAI** (airgap LLM-as-a-service: OpenAI-compatible API, llama-cpp/GGUF CPU + vLLM GPU, Whisper, embeddings, RAG/ChromaDB). **Archived Feb 2025 → treat as a reference pattern, not a hard dependency.** Wrap our explainer in an **OpenAI-compatible endpoint** to align; default to **llama-cpp/GGUF on CPU** (no GPU guaranteed at sea). Our ONNX + distributed edge vector store is *our* build (LeapfrogAI doesn't advertise ONNX or distributed-fleet vector DB) — we **extend** the pattern, not compete.

## Recommended architecture — "Theseus-on-UDS"
```
DISCONNECTED HULL (SWAN-side, airgap)
  UDS Core (K8s) — inherited/hardened/monitored:
    Istio mTLS · Keycloak+Authservice (human-in-command RBAC) · Falco · Loki/Vector ·
    Prometheus/Grafana · Velero · Pepr UDS-Operator (default-deny)
    └── THESEUS UDS Package (Zarf pkg + UDS Package CR):
         • Local Anomaly Cell  → PyTorch/ONNX models in Podman/OCI images (digest-pinned)
         • LLM Explainer        → OpenAI-compatible (llama-cpp/GGUF default) + local RAG
         • Tamper-evident record → append-only, Velero-snapshotted
         • Custom Pepr module    → no-egress explainer, append-only record, human-in-command gate
         • Decision-support UI   → Istio VirtualService + Keycloak SSO
  Delivery: signed UDS Bundle (cosign) → DU+Leidos OTA rail → deploy offline
  Build (connected): zarf package create (flatten images, SBOM, sign) → UDS Registry (IL6+) → carry → deploy
```

## Partnership pitch (why DU wants Theseus on their stack)
1. **Proves the AI-at-the-edge thesis on a hull** — a flagship afloat AI mission app running inside UDS, disconnected: exactly the story their Navy/CANES motion needs.
2. **Fills their published AI gaps** — LeapfrogAI is archived w/ no ONNX or distributed-fleet vector DB; Theseus *extends* the pattern (complementary catalog package, not competition).
3. **Makes the UDS Registry "app store" more valuable** — a credible accredited-on-UDS naval analytics reference deployment.
4. **Warhacker-native** — DU hosts the event; shipping Theseus as a UDS Package is the lowest-friction way into their ecosystem + co-marketing.

## Immediate technical actions
1. Author `zarf.yaml` + `uds.yaml`; pin images by digest; emit/retain SBOM; cosign-sign.
2. Define the Theseus **UDS `Package` CR** (Istio routes, default-deny egress, Keycloak client, Prometheus scrape).
3. Write the **custom Pepr policy module** (no-egress explainer, append-only records, human-in-command gate) — highest-leverage, lowest-cost differentiator + safety artifact.
4. Wrap the explainer in an **OpenAI-compatible API**; default llama-cpp/GGUF CPU.
5. **Verify with DU directly:** current maintained AI offering (post-LeapfrogAI-archive), UDS Core's actual IL/ATO status, path to list in the UDS Registry / ride the Leidos OTA shipboard test. **Use the Justin Hodges (NIWC Atlantic RCC) relationship.**

## Caveats
High confidence: UDS Core composition, Zarf/Pepr mechanics, CANES + Navy/Leidos OTA, UDS Army ATO-inheritance, Warhacker. **Flagged (build-side / verify with DU):** LeapfrogAI maintenance post-archive; ONNX in LeapfrogAI; distributed edge vector-DB reference; a discrete IL5/IL6 ATO for UDS Core itself (the pitch is *control inheritance + 800-53 coverage + auto artifacts*, not a turnkey IL stamp).
