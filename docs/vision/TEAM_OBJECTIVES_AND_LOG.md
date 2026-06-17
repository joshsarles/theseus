# THESEUS — Team Objectives & Living Log
*The single source of truth for what the team is building. Update the LOG section as the Slack convo evolves.*

## Team objectives (pinned by Tommy Do, team-theseus Slack)
1. **Deploy AI models at the edge** (resource-limited, shipboard-like environment)
2. **Centrally manage models at the edge**
3. **Allow live model updates via training from users at the edge**
4. **Allow staging model updates from "shore side" without sneakernetting**

→ In Theseus terms: this is the **edge model-delivery & lifecycle spine** — exactly the "Airgap Native Model Delivery" problem, made DDIL-native. It's the substrate; the **anomaly cell** (NV063 — AIS/ADS-B/radar Pattern-of-Life) is the showcase model that rides on it; the **tamper-evident record** is the moat (every model load/update/decision sealed).

## Stack (team-decided in Slack)
- **Python 3.14.4** — the runtime (stdlib spine + ML). Verify MLflow 3.13 / PyTorch wheels resolve on 3.14 before pinning the container base; if a wheel lags, run a 3.13 base image + 3.14 where it's clean.
- **MLflow 3.13** (latest; ≥3.11 avoids the high-sev CVE) — central server in a container = **model registry + tracking + monitoring** of models running on other containers / the Pi nodes. This is objectives #2/#3/#4.
- **Podman** (latest; >5.8.1 avoids CVE) — rootless/daemonless OCI container build + runtime. *No Docker.*
- **Raspberry Pi cluster** — the edge nodes (resource-limited, shipboard-analog). Deploy models here; test save/update.
- **UDS / Zarf** — airgap bundle for "shore-side staging without sneakernet" (the deploy spine, already verified).
- **Tamper-evident record** — every model version + update + decision sealed (the trust layer / accreditation evidence).
- **PyTorch** (train) → **ONNX** (edge inference). **Force OS** = agent orchestration option (APOLLO proving on Blackwell + Kimi 2.7).

**Hardware reality (Nick Bernstein, Slack):** EdgeRunner Light needs ~8GB VRAM — unrealistic for our nodes. Use small/edge models instead: **BitNet** (~8 tok/s, tiny footprint), Gemma 3 1B, Qwen2.5 1.5B, or **distributed inference** (exo / distributed-llama) across the cluster. Pi 5 + AI HAT+2 (40 TOPS) raises the per-node ceiling.

**Offline-build note (Tommy Do):** can't pull the MLflow ghcr image before the venue internet dies → **pre-stage** the image, or build from `python-slim` (Dockerfile.full). Pre-staging models/images is the *whole point* of objective #4.

## How the team build maps to the strategy (so we stay aligned)
- **What the team is building (v1 demo):** MLflow central server (Podman) ↔ models deployed on the Pi cluster ↔ live update from the edge ↔ staged from "shore" via a UDS bundle, no sneakernet. Demoable + maps to the "Airgap Native Model Delivery" use case.
- **The showcase model on top:** the **anomaly cell** (AIS/ADS-B Pattern-of-Life) → maps to **NV063** (opens 6/24).
- **The moat:** the **tamper-evident record** — every model promotion/rollback + every alert/decision sealed = accreditation evidence. (Build the evidence layer like it's the company.)
- **The honest framing (carry everywhere):** onboard **decision-support, human-in-command, SWAN-side**, integrate-not-replace, real-not-mock. Not "autonomous ship control."
- **Full architecture + build decision:** see `../vision/BUILD_VISION.md`. SBIR demand: `../research/sbir/NAVSEA_SBIR_TOPICS.md`.

---

## LOG — update as we go (newest on top)
*Append Slack decisions / progress here. Format: `### <date> — <topic>` then bullets.*

### Jun 17 — hardware confirmed + master roadmap
- Real edge hardware: **2× Raspberry Pi 5, 4GB**. Maps to **2 organs** — Pi-1 MACHINERY (CBM), Pi-2 CONTACTS (AIS PoL). 4GB ⇒ small models only on the edge; heavy reasoning on Tier-1 (Blackwell).
- Master **`ROADMAP.md`** created at repo root (living; phases 0–3). Tactical board stays `KANBAN.md`.

### Jun 17 — platform + compute clarified (founder)
- Target = **big surface combatants (DDG/CG)** with real onboard compute — NOT compute-starved edge.
- **Two-tier compute** (both aboard): Tier-1 ship GPU brain (fusion + explainer + onboard retrain + record) and Tier-2 Pi system-components (per-subsystem sensing/detection). Pi cluster = the sensing subset, not the whole brain. → `../architecture/COMPUTE_TIERS.md`.
- **Emulation:** founder's **NVIDIA Blackwell cloud** stands in for the ship's Tier-1 compute; real Pis are the Tier-2 components.
- Inference corrected: GPU (Triton-TRT-LLM, `iron-bank` flavor) runs ON the ship Tier-1; GGUF/llama.cpp on the Pi components. vLLM Iron Bank is out (archived). FIPS = crypto boundary only. → `../integration/INFERENCE_AND_FIPS.md`.

### Jun 17 — team formed + stack locked
- team-theseus channel created; ~12 members (NAVSEA/NIWC engineers + analysts). KanBan stood up (Carolina Hatch, Juan Pineda).
- Stack decided: MLflow 3.13 central server + Podman + Pi cluster. CVE-aware (MLflow ≥3.11, Podman >5.8.1).
- Architecture sketch (Juan Pineda / Tommy Do): MLflow container as central server monitoring models on other containers/Pis; deploy a model to the Pis; test save + update; stage updates shore-side.
- Repo live + public: github.com/joshsarles/theseus. Working dir: /Developer/Theseus.
- *(next: pick the first model to deploy on the Pis; pre-stage MLflow image before internet dies; wire the record.)*
