# THESEUS demo — the model-delivery loop

**The workflow:** `Stage Operational Data → Retrain → Update local model` — every step sealed into the tamper-evident record, ending with an offline verify. This is objectives #1–#4 made runnable, and it's the spine the whole team plugs into.

## Run it (Python 3.14, zero required deps)
```bash
bash demo/run.sh
# or step by step:
python3 demo/stage_data.py     # 1. stage operational data  -> seals data_staged
python3 demo/retrain.py        # 2. retrain + register v(N)  -> seals model_trained
python3 demo/update_model.py   # 3. promote to local + verify -> seals model_promoted
```
Run it again → a new version trains, promotes, the previous is kept for **rollback**, and the record grows. It works **offline** (stdlib least-squares fallback) and gets better with the real stack:
- `pip install scikit-learn` → real GradientBoostingRegressor (auto-detected).
- `export MLFLOW_TRACKING_URI=http://<server>:5000` → logs to Tommy's central MLflow.
- Real data: `demo/data/staged.csv` is the **real UCI #316** naval gas-turbine CBM set (see `data/SOURCE.md`). RMSE ~0.0038 predicting compressor decay.

## The AIS Pattern-of-Life cell (the NV063 beat) — `ais_pol.py`
```bash
python3 demo/ais_pol.py            # runs on real MarineCadastre AIS (data/datasets/, gitignored)
python3 demo/ais_pol.py --box 25,31,-82,-79   # bound to an OPAREA (e.g. Florida Straits)
```
**Cold-start, no historical DB** (NV063's hardest requirement): the "normal" speed envelope is learned **in-situ** from the op-area's own traffic, then deviations are flagged with a plain-language **why + recommended action** and sealed into the record. Detects **loiter / AIS-dark-gap / position-jump (spoof) / overspeed**. ~1.5M real AIS rows in ~4s, fully explainable. *(Loiter thresholds are tunable — busy ferry terminals still dwell; tighten per OPAREA.)* This is the 2nd model on the same delivery spine, proving it's model-agnostic.

## The watchstander board — `show.py`
```bash
bash demo/run.sh && python3 demo/ais_pol.py && python3 demo/show.py
```
Renders the human-in-command surface from what's sealed in the record: machinery (CBM) model health, flagged contacts as **RECOMMEND → ACCEPT/OVERRIDE** cards (why + recommended action), and record integrity (verify PASS). *Theseus recommends; the watch officer decides; nothing is actioned automatically* — the rails, made visible. This is the demo's closing view.

## The three contracts (so every lane plugs in without colliding)
1. **Data** — `stage_data.py` writes `demo/data/staged.csv` (last column = target `gt_compressor_decay`). Swap in ship HM&E telemetry or a live SDR AIS capture; keep the CSV shape.
2. **Model** — `retrain.py` registers `theseus-cbm/v{N}` (local registry + MLflow). The edge pulls the latest.
3. **Record** — `_record.seal(out_dir, kind, obs_id, dict)` appends one hash-chained leaf. **Every lane seals its step** → one provable audit trail (the moat / accreditation evidence).

## What maps to what
- `stage_data.py` → **THESEUS-agent data lane / William's SDR rig** (the cold-start capture).
- `retrain.py` → **Tommy's MLflow build** (train/register/version).
- `update_model.py` → **William's Pi** (pull → promote → rollback-ready → seal). This is what runs on the edge node.
- `_record.py` / `referee/chain.py` → **WARHACKER's trust layer** (the tamper-evident record).

## Production path
Containerize each step (Podman), ship as a UDS/Zarf bundle (`docs/integration/DEFENSE_UNICORNS.md`), pre-stage models so nothing pulls at sea, and let a Pepr policy enforce human-in-command + append-only-record at the cluster.
