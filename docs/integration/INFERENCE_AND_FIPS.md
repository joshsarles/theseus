# THESEUS — Inference Engine & FIPS Posture
*Jun 17 2026, sourced. Answers: "vLLM from Iron Bank? Is it FIPS compliant?" Short version: **no to Iron Bank vLLM (archived); yes to Triton-TensorRT-LLM for shore GPU + llama.cpp/GGUF for the edge**; FIPS covers the crypto boundary, not the model.*

## The two tiers (and what runs where)
| Tier | Job | Engine | GPU? | Image |
|---|---|---|---|---|
| **Ashore / GPU** | the LLM explainer at scale; retrain-ashore | **Triton + TensorRT-LLM** | yes | **Iron Bank, actively maintained** (e.g. `server-24-tensorrt-llm`, v26.02) |
| **Shipboard / edge (Pi)** | single-user, latency-critical, DDIL | **llama.cpp + GGUF** (or llamafile) | no | FIPS-mode UBI base; static/CPU |
| Local dev only | model iteration | vLLM ok on a laptop | yes | not for hardened Navy deploy |

DU's own LeapfrogAI uses exactly this split (vLLM/Triton on GPU, llama.cpp on edge).

## Why NOT Iron Bank vLLM
- The two Iron Bank vLLM images are **archived / read-only**: `darksaber/niprgpt/vllm` (Jan 2024) and `opensource/defenseunicorns/leapfrogai/vllm` (Aug 2024). No recent hardening updates.
- vLLM shipped **6+ high-sev CVEs in 2025–2026** (e.g. CVE-2025-30165 RCE via pickle in multi-node ZeroMQ; CVE-2026-25960 SSRF). Rebuilding it means owning that maintenance.
- The **actively maintained** Iron Bank GPU-LLM path is **Triton + TensorRT-LLM** (NVIDIA security team) — lower-friction, current, Iron-Bank-ready.

## FIPS — the honest framing (use this in proposals/ATO)
FIPS 140-2/140-3 validates **cryptographic modules**, *not* an inference server or model.
- **In scope:** the OS crypto — RHEL 9 UBI ships the **CMVP-validated OpenSSL 3.0 FIPS provider (cert #4746)**. Run the container in **FIPS mode** → TLS/SSH/key-ops to the inference server are FIPS-compliant.
- **Out of scope:** Python, PyTorch, CUDA kernels, model weights, the inference itself. None of that is "FIPS validated" and you must not claim it is.
- **vLLM gotcha (if ever used):** it defaults to **Blake3** (not FIPS-approved); set `VLLM_MM_HASHER_ALGORITHM=sha256`; its MD5 calls use `usedforsecurity=False` and fall back to SHA-256 under FIPS OpenSSL.
- **Edge (llama.cpp) caveat:** the FIPS boundary is the host libc/OpenSSL, not llama.cpp code. Some contracts demand validated crypto throughout the stack — verify with the C&A office.

**The exact line for the proposal/ATO:**
> "Theseus's inference stack operates in a FIPS 140-3 compliant cryptographic environment (RHEL UBI FIPS mode, OpenSSL 3.0 FIPS provider, CMVP #4746). FIPS validation applies to the cryptographic boundary (TLS, SSH, key operations), **not** the model inference itself."

## UDS ↔ Iron Bank (the ATO lever)
- UDS Core supports image **flavors**: `upstream` / `iron-bank` / `unicorn`. Building a Theseus UDS package on the **`iron-bank` flavor** inherits DoD STIG hardening at the image layer.
- Your ATO references Iron Bank's CAR for the base layer (don't re-document it); scanners verify your app layer adds no new exploitable CVEs. **But:** Iron Bank assesses, it doesn't authorize — you still need your own accreditor. Image pull needs DoD creds (P1 SSO + Harbor).
- Ties directly into the ATO-inheritance story in `DEFENSE_UNICORNS.md`.

## Recommendation for Theseus
1. **Shore/GPU explainer → Triton + TensorRT-LLM (Iron Bank).** Not archived vLLM.
2. **Edge/Pi → llama.cpp + GGUF** (validate a Q4_K_M model on representative hardware before claiming latency SLAs).
3. **FIPS posture → "FIPS-mode crypto boundary, model unvalidated"** — never "FIPS-compliant inference."
4. Build UDS packages on the **iron-bank flavor**; reference the Triton CAR in ATO evidence.

## Caveats
vLLM hardening currency (archived); llama.cpp FIPS scope is OS-only (verify per contract); UDS→Iron Bank ATO linkage is site-specific (work with C&A); no Navy-shipboard Triton reference found (treat as COTS-adjacent risk). Iron Bank links require DoD SSO. Sources: repo1.dso.mil Iron Bank (vLLM archived / Triton-TRT-LLM active), CMVP cert #4746, vLLM security advisories, UDS Core flavor docs, Red Hat FIPS/vLLM-vs-llama.cpp guidance.
