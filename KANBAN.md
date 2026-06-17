# THESEUS — Kanban
*Living board. Mirror of the team-theseus Slack KanBan + the build tasks. Move cards as we go.*

## 🎯 The demo (what "done" looks like for Warhacker)
A central **MLflow** server (Podman) manages models deployed to a **Raspberry Pi cluster** (shipboard-analog edge). Models update **live from the edge** and stage **from shore via a UDS bundle — no sneakernet**. The showcase model: a real **naval gas-turbine decay** model (UCI #316) and/or an **AIS Pattern-of-Life** anomaly model → explainable alert → sealed in the **tamper-evident record**. Pull the network cord → it keeps running (DDIL).

---

## ✅ Done
- Team formed (~12: NAVSEA/NIWC engineers + analysts); team-theseus Slack + KanBan up.
- Stack decided: MLflow 3.13 + Podman (latest) + Pi cluster + UDS/Zarf + Python 3.14.4.
- Repo live + public: github.com/joshsarles/theseus → cloned to /Developer/Theseus.
- Research documented: build vision, SBIR (NV063), **datasets (full A–F catalog)**, MLflow/Podman runbook, DU integration, IL roadmap.
- **🟢 DEMO LOOP RUNS** — `bash demo/run.sh`: Stage→Retrain→Update on **real UCI #316** (RMSE ~0.0038), every step sealed, record verify PASS, rollback kept.
- **Lanes mapped** (`docs/TEAM_LANES.md`) — everyone has a lane + a today/tomorrow plan.

## �� In progress
- MLflow central server in a Podman container (runbook: `docs/setup/MLFLOW_PODMAN.md`).
- Pick the first model + dataset (recommended: UCI #316 naval gas-turbine — see `docs/research/datasets/DATASETS.md`).

## 📋 Backlog — model-delivery spine (objectives #1–#4)
- [ ] **Pre-stage the MLflow image offline** (`podman save/load`) BEFORE venue internet dies — *urgent*.
- [ ] Deploy a model to the Pi cluster (PyTorch → ONNX); register in MLflow.
- [ ] Test **save + update** a model from a Pi (live edge update — objective #3).
- [ ] **Shore-side staging**: bundle a new model version into a UDS/Zarf package → deploy to airgap, no sneakernet (objective #4).
- [ ] Rollback-to-last-good on a node under DDIL (local, no shore).

## 📋 Backlog — the model + the moat
- [ ] Train the **gas-turbine decay/RUL** model on UCI #316 → register → deploy to a Pi.
- [ ] **AIS Pattern-of-Life** anomaly model (NOAA MarineCadastre train / OMTAD eval); live AIS via SDR at venue → explainable alert (NV063).
- [ ] Wire the **tamper-evident record**: seal every model promotion/rollback + every alert/decision (the moat).
- [ ] **Console**: live ship-state + the recommend → human accept/override beat.

## 📋 Backlog — deploy + demo
- [ ] UDS/Zarf airgap bundle (image + models + config) — `make deploy-local` analog for Theseus.
- [ ] DDIL beat: pull the cord, show it keeps running + the record holds.
- [ ] Demo script + 60-sec recorded fallback.

## 🧭 Rails (every card honors these)
Human-in-command · decision-support, not autonomous control · SWAN-side data only (combat is air-gapped) · integrate-not-replace · real, not mock.

## 🔗 Map
Objectives + live log: `docs/vision/TEAM_OBJECTIVES_AND_LOG.md` · Build decision: `docs/vision/BUILD_VISION.md` · SBIR: `docs/research/sbir/NAVSEA_SBIR_TOPICS.md` · Datasets: `docs/research/datasets/DATASETS.md` · MLflow: `docs/setup/MLFLOW_PODMAN.md`
