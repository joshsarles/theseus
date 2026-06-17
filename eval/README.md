# THESEUS — anomaly eval harness (NV063)

Scores anomaly predictions against a labeled set → **precision / recall / false-alarm rate / F1**. The false-alarm rate is the number the NV063 strategy hinges on (trust is a one-shot resource on a ship — target **< ~1 nuisance alert per watch**).

```bash
python3 eval/score.py --pred predictions.csv --labels labels.csv --out metrics.json
python3 eval/score.py --selftest      # verifies the scoring math (passes)
```

## The prediction contract (so `demo/ais_pol.py` emits a matching file)

**predictions.csv** — one row per evaluated track:

| column | required | meaning |
|---|---|---|
| `track_id` | ✓ | vessel id (MMSI). Must match the label set's `track_id`. |
| `is_anomaly` | ✓ | `1` if the cell flagged this track, else `0`. |
| `score` | optional | confidence in `[0,1]` (for future threshold sweeps / PR curves). |
| `kind` | optional | `loiter` / `dark_gap` / `position_jump` / `overspeed` (for error analysis). |

**labels.csv** — the ground truth (e.g. OMTAD): `track_id,is_anomaly`.

Scoring rule: the **label set defines the universe**. A track in the labels with no positive prediction (absent from predictions, or `is_anomaly=0`) counts as not-flagged. `false_alarm_rate = FP / (FP + TN)`. Positive predictions for `track_id`s absent from the labels are reported as `unscored_positive_predictions` (not counted in P/R) so coverage gaps are visible.

### How `ais_pol.py` plugs in
`demo/ais_pol.py` already detects per-track anomalies and seals `ais_anomaly` leaves (`{mmsi, type, confidence, ...}`). To feed this harness, emit one `predictions.csv` row per flagged track: `track_id=mmsi`, `is_anomaly=1`, `score=confidence`, `kind=type`. (WARHACKER's lane: `ais_pol.py` emits to match this contract.)

## Labels status (HONESTY-FIRST)
- The harness is **label-source-agnostic** — any `(track_id, is_anomaly)` set works.
- **OMTAD** (the purpose-built maritime-anomaly benchmark) is the intended NV063 label source, but its data artifact + license are **UNVERIFIED / pending acquisition** (see `docs/research/datasets/DATASETS.md` §6 and `A_AIS_MARITIME_REPORT.md`). Until it lands, validate the scorer with `--selftest`, and treat any run against `marinecadastre.py`'s `weak_anomaly_heuristic` as a **sanity check only** (weak labels are rule-distilled, not ground truth — never a headline NV063 number).
- Global Fishing Watch dark-vessel/loitering labels are richer but **NON-COMMERCIAL** — usable for internal method validation only, never in a shipped/SBIR deliverable.

Rails: synthetic-vs-real stated; advisory/decision-support framing (predictions cue a watchstander; human-in-command).
