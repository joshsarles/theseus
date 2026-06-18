# THESEUS — Rollback Point (the safe baseline)

*If the fleet-learning pivot is vetoed (team or judges) tomorrow, this is the known-good state to return to. The one-ship demo stands on its own and is unaffected by the pivot.*

## The baseline
- **Repo:** `github.com/joshsarles/theseus` (public, AGPL-3.0), branch **`main`**.
- **Local clone:** `/Users/force/Developer/Theseus`.
- **Rollback tag:** **`event-baseline`** → commit **`41afc03`** (pushed to origin/main).
- **What it is:** the verified, working **one-ship THESEUS demo** — judge self-audit **6.9/10**. All real, on real data:
  - `bash demo/run.sh` — Stage→Retrain→Update loop (real UCI #316, RMSE 0.0038), sealed.
  - `demo/ais_pol.py` — cold-start AIS Pattern-of-Life (NV063), cross-region validated, honest eval 0.57/0.70/0.15.
  - `frontend/ui` (:5173) — the CIC dashboard (record-as-spine, live ACCEPT/OVERRIDE seal).
  - Real airgap **UDS deploy** (Zarf signed pkg + SBOM + cosign + live Pepr admission).
  - Edge serve + shore→ship delivery, ONNX edge inference, MLflow sync, ship hierarchy, real explainer LLM, DDIL beat.
  - **21 tests pass.**

## What is "the pivot" (additive — revertable without touching the working demo)
- **Docs:** `docs/vision/FLEET_LEARNING_VISION.md`, `docs/INTEGRATION_SPEC.md`, the ROADMAP ★ North Star section.
- **Demonstration:** the fleet-learning miniature (2 Pi subsystems → ship brain → fleet brain on Blackwell; provenance-gated merge; reject-a-poisoned-delta-live). Built as *additional* beats — the one-ship demo runs without it.

## How to roll back (if vetoed)
- **Present the one-ship demo only:** just don't run the fleet beats — nothing to revert; the working demo is intact.
- **Revert the pivot entirely:** `git checkout event-baseline` (detached) to inspect, or revert the additive commits. Do NOT `git reset --hard` on the shared working tree (it moves all agents) — use a `/tmp` worktree for any history surgery.
- **The overnight HARDENING is NOT the pivot** — atomic seal, Pepr record-binding, cold-start fix, explainer grounding, preflight gate all *improve the baseline* and should be kept regardless of the pivot decision.

## Why the pivot is low-risk to try
The fleet-learning work is **additive layers + a demonstration**, not a rewrite. The worst case is "present the one-ship demo," which is already a 6.9 and competitive on the heaviest rubric axes. The pivot only changes *what we're graded as* (a category vs a tool) — it cannot break what already works.
