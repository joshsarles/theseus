# theseus-uuv AE receiver

Edge container serving the BlueROV2 Conv1d sequence autoencoder for the THESEUS
destroyer fleet.  Speaks the same HTTP contract as every other `analytics:latest`
River node so it slots in as container #8 (UUV OWN-SYSTEMS) without touching
the existing feeder or API code.

---

## HTTP contract

| Method | Path          | Body / Query                             | Returns                              |
|--------|---------------|------------------------------------------|--------------------------------------|
| GET    | /health       | —                                        | model identity, threshold, n_channels |
| POST   | /stream-item  | `{topic_id, data:[{<ch>:v,...}]}`        | `{status, window_full, last_score}`  |
| GET    | /history      | —                                        | list of scored windows (cap 100)     |

The `active_anomaly_score` field in each history record is in [0,1] — the same
field the ship API reads via `_node_latest_score` on every River node.

---

## Inference

- Model: `models/onnx/uuv_seq_ae.onnx` (Conv1d autoencoder, fp32, 567 KB)
- Channels: 23 ArduSub onboard telemetry channels (see `models/uuv/results.json`)
- Window: 64 samples (6.4 s at 10 Hz)
- Threshold: 0.417558 (shipped default from `results.json`)
- Score: mean per-element reconstruction MSE; flagged when score >= threshold
- Missing channels: imputed with the training mean from `scaler.json`
- Top channel: the channel with highest per-channel MSE — returned per window
  for watchstander explainability

No torch, no sklearn, no pandas.  `numpy + onnxruntime` only.

---

## Build

```bash
# From the Theseus repo root:
docker build --platform linux/arm64 -t uuv-ae:latest serve/ae-receiver/
```

The ONNX, scaler.json, and results.json are baked into the image under /model.
To override at runtime, bind-mount a directory:

```bash
docker run -v /path/to/your/model:/model ...
```

---

## Run

```bash
# Standard fleet port 54547 (external) -> container port 54321
docker run -d --name uuv-ae -p 54547:54321 uuv-ae:latest
```

Health check:

```bash
curl http://127.0.0.1:54547/health
```

Environment overrides:

| Variable      | Default                    | Purpose                        |
|---------------|----------------------------|--------------------------------|
| ONNX_PATH     | /model/uuv_seq_ae.onnx     | ONNX model path                |
| SCALER_PATH   | /model/scaler.json         | Per-channel mean/std           |
| RESULTS_PATH  | /model/results.json        | Channel list + threshold       |
| MLFLOW_URI    | ""                         | Echoed in /health (read-only)  |
| HISTORY_CAP   | 100                        | Max history entries kept       |

---

## Feed (synthetic)

`feed_ae.py` generates 23-channel records sampled from the training
distribution and injects one anomaly every 6 records (ANOMALY_EVERY=6,
spike 5 channels at ±6σ).  Requires `numpy` locally.

```bash
# Send 80 records at 0.2s intervals (fills a window after record 64)
python3 serve/ae-receiver/feed_ae.py \
  --url http://127.0.0.1:54547/stream-item \
  --interval 0.2 \
  --n 80

# Check scored windows
curl http://127.0.0.1:54547/history | python3 -m json.tool
```

Expected separation:
- Normal windows: `active_anomaly_score` < 0.5 (raw MSE well below 0.42)
- Anomaly windows: `active_anomaly_score` > 0.5, `flagged: true`

---

## Fleet integration

The existing ship API reads `history[-1]["active_anomaly_score"]` from each
node.  This container returns that field in every history record.  Register
it in the fleet compose/config under name `theseus-uuv` at port 54547.
