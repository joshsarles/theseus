# How `theseus-uuv` works

*A mechanics-level walkthrough of the UUV own-systems sequence autoencoder: how raw BlueROV2
telemetry becomes an anomaly score on a Raspberry Pi. For **what changed / results / caveats**, see
[`README.md`](README.md); for the **test methodology**, see `test_uuv_ae.py`. This file is the "how
does it actually work" explainer.*

---

## The one-sentence idea

> Teach a small neural network to **reconstruct a few seconds of a healthy UUV's telemetry**; at
> runtime, anything it **can't reconstruct well** is flagged as anomalous — because the network has
> only ever seen normal behaviour, so a fault it never learned shows up as a large reconstruction error.

This is **reconstruction-error anomaly detection** with an **autoencoder**. It needs **no fault
labels to train** (you only need normal operating data), which is exactly what a UUV cut off from
comms under DDIL can rely on: it learns *its own* notion of "normal" and watches for deviation.

---

## 1. Input: from raw logs to standardized windows

### 1a. The 23 channels (`ingest/ardusub.py`)
The BlueROV2 / ArduSub logs are many separate per-channel CSVs logged at slightly different times.
The adapter resamples them onto **one common 10 Hz grid** (linear interpolation) and keeps only the
**onboard subsystem channels** a real UUV carries — 23 of them:

```
attitude   : att_roll, att_pitch, att_yaw, att_roll_speed, att_pitch_speed, att_yaw_speed   (6)
IMU        : imu_xacc, imu_yacc, imu_zacc, imu_xgyro, imu_ygyro, imu_zgyro                   (6)
energy     : batt_voltage                                                                    (1)
propulsion : thr1 … thr6   (the 6 vectored thruster PWM outputs)                             (6)
pressure   : press_int, temp_int  (internal barometer / leak indicator)                      (2)
             press_ext, temp_ext  (external / depth)                                         (2)
```
Output: `ingest/out/ardusub.csv`, one row per 10 Hz time-step, grouped by `recording`.

### 1b. Windowing
The model doesn't look at single instants — it looks at **6.4-second windows** (W = 64 samples at
10 Hz). A window is a small multivariate time series:

```
one window  =  matrix of shape (C=23 channels, W=64 timesteps)
```

Windows are cut **within a single recording** (never spanning two recordings), sliding by a stride
(8 samples in training for dense coverage, 16 for evaluation). The temporal structure inside the
window — *how the channels move together over 6.4 s* — is the signal the model learns.

### 1c. Standardization
Each channel is **z-scored** (subtract mean, divide by std) using statistics computed on the
**training windows only** (no peeking at validation/test). Constant channels (e.g. an idle thruster
that never moves) get a std-floor of 1.0 so they don't blow up. After this, every channel is roughly
mean-0 / unit-variance, so the loss isn't dominated by whichever channel happens to have big raw units.

```
standardized = (raw − channel_mean) / channel_std      # mean/std saved in scaler.json
```

---

## 2. The architecture: a length-preserving 1D-Conv autoencoder

An **autoencoder** has two halves: an **encoder** that squeezes the input down to a small "bottleneck"
summary, and a **decoder** that tries to rebuild the original input from that summary. If the
bottleneck is small, the network is *forced* to learn the dominant patterns of normal data rather
than memorize.

```
INPUT  (23 channels × 64 timesteps)
        │
   ┌────▼─────────── ENCODER ───────────────┐
   │ Conv1d(23 → 32, kernel 5, pad 2) + ReLU │   local temporal patterns, per-channel mixing
   │ Conv1d(32 → 16, kernel 5, pad 2) + ReLU │   (length stays 64 — padding preserves it)
   │ Flatten  → 16 × 64 = 1024 numbers       │
   │ Linear(1024 → 64)                       │   ← BOTTLENECK: compress to 64 numbers (16× squeeze)
   └────┬────────────────────────────────────┘
        │  latent vector z  (64 numbers = the window's "summary")
   ┌────▼─────────── DECODER ───────────────┐
   │ Linear(64 → 1024) → reshape to (16,64)  │
   │ Conv1d(16 → 32, kernel 5, pad 2) + ReLU │
   │ Conv1d(32 → 23, kernel 5, pad 2)        │
   └────┬────────────────────────────────────┘
        │
OUTPUT (23 channels × 64 timesteps)  = the reconstruction
```

**Why this shape, specifically:**
- **`Conv1d` (1-D convolution along time)** slides a 5-sample kernel across the window, so it learns
  *local temporal patterns* (a thruster ramp, an attitude wobble) and mixes channels — the right
  inductive bias for telemetry. Padding (`pad 2` for `kernel 5`) keeps the length at 64 throughout,
  so input and output shapes always match and there's no resampling to get wrong.
- **The `Linear(1024 → 64)` bottleneck** is the squeeze that forces generalization. It's also the
  layer that **`int8` quantization accelerates** (a big matrix multiply) — which is why int8 gives a
  real size win here, unlike a tree model.
- **Conv1d + Linear were chosen over LSTM/GRU** because they **export to ONNX cleanly**; LSTM is
  finicky and GRU isn't even quantizable in onnxruntime. (See `README.md` for the verification.)

Total: a small model — fp32 ONNX ≈ 567 KB.

---

## 3. Training: learn to rebuild *normal*

```
for each training window x (nominal only):
    x_hat = model(x)                      # the reconstruction
    loss  = mean( (x_hat − x)² )          # MSE: how wrong was the rebuild?
    backprop, Adam step
```

- **Trained on nominal windows only.** The model never sees a fault during training. It becomes good
  at rebuilding healthy telemetry and (by construction) *bad* at rebuilding anything unusual.
- Adam optimizer, learning rate 1e-3 with cosine decay, 200 epochs, batch 256, seed 316
  (deterministic — same inputs reproduce the same weights). Training MSE drops ~0.98 → ~0.06.
- Recording-level train/val/test split so windows from one recording never leak across splits.

---

## 4. Scoring: reconstruction error = anomaly score

At runtime, for any window `x`:

```
anomaly_score(x) = mean over (channels × timesteps) of ( model(x) − x )²
```

- A **healthy** window → the network rebuilds it well → small error → **low score**.
- A **faulted** window (a stuck thruster, a sagging battery, rising internal pressure) → the network
  has never learned that pattern → rebuilds it poorly → large error → **high score**.

The *same* formula runs in training, in the test harness, and on the Pi — so the deployed scorer is
identical to the trained one (verified: ONNX vs torch agree to ~3e-7).

A useful side-effect: looking at **which channels** carry the most reconstruction error hints at
*which subsystem* deviated. Treat this as a **sanity check, not a diagnosis** — an autoencoder's
error is naturally largest on the channel that was perturbed, so it confirms "something is off in the
thrusters/battery/etc." rather than pinpointing a root cause.

---

## 5. The threshold: how a score becomes an alarm (in-situ calibration)

A score alone isn't an alarm — you need a cutoff. The honest, deployment-realistic way (matching the
project's **cold-start** philosophy) is **in-situ calibration**:

```
1. On deployment, observe the vehicle's OWN nominal telemetry for a while (its baseline).
2. Set the threshold at a high quantile (e.g. the 98th percentile → ~2% target false-alarm rate)
   of the reconstruction error on that baseline.
3. Thereafter: score each new window; flag it if score > threshold.
```

Why per-vehicle and not one global number: reconstruction error varies a lot between vehicles/runs
(in our data, ~8.7× across recordings), so a single global threshold over-fires on energetic runs and
under-fires on quiet ones. Calibrating on *this* vehicle's own baseline normalizes that away. A
`scaler.json` ships a default threshold, but deployment should re-calibrate in-situ.

> **Honesty note:** evaluation faults are **synthetic** (real telemetry is all nominal), so reported
> detection numbers are illustrative, not fielded performance. See `README.md` → "Independent test".

---

## 6. Inference and edge deployment

### Export
```
PyTorch model ──torch.onnx.export(opset 17)──▶ uuv_seq_ae.onnx   (fp32, 567 KB)
                       └─quantize_dynamic(int8)─▶ uuv_seq_ae_int8.onnx (154 KB)
```

### Serving (`models/uuv/infer.py`) — the torch-free runtime
```
every 100 ms (10 Hz), once a fresh 64-sample window is available:
   window (23×64) ──standardize (saved mean/std)──▶ onnxruntime InferenceSession (1 thread)
                  ──▶ reconstruction ──▶ score = mean((recon−window)²)
                  ──▶ score > threshold ?  → advisory anomaly flag (human decides)
```
`infer.py` is the deployable entry point. It imports **only numpy + onnxruntime** (no torch /
sklearn / pandas) — verified by running it with those modules blocked. `--calibrate` sets the alarm
threshold **in-situ** from the first half of the stream (the cold-start story, §5).

### Running on a Raspberry Pi 5 — **4 GB *or* 8 GB**
RAM is **not** the constraint (the model uses ~52 MB), so **both the 4 GB and 8 GB Pi 5 run this
identically** — the 8 GB only adds spare headroom. What actually matters on a Pi:

| Concern | Status |
|---|---|
| **CPU arch** | `aarch64`. **Prerequisite: 64-bit Raspberry Pi OS** (`uname -m` → `aarch64`); the 32-bit ARMHF default OS has no wheels. |
| **Dependencies** | `numpy` + `onnxruntime` only — both ship aarch64 manylinux wheels. Install: `pip install -r models/uuv/requirements-pi.txt`. No build-from-source, no torch. |
| **Model size / RAM** | int8 ONNX **154 KB**, **~52 MB RSS** → fits 4 GB with >70× margin. |
| **Latency** | sub-ms/window single-thread; a window arrives every 100 ms → **>600× real-time headroom** on one core. **int8 is recommended on ARM** — the Pi 5's Cortex-A76 has the dot-product (SDOT/UDOT) extension that accelerates int8 (unlike x86 dev boxes, where int8 can be slower; confirm on-device). |
| **Threads** | defaults to 1 (`--threads 1`); the 8 GB Pi can raise it, but it's already vastly real-time at 1. |

```bash
# on a 64-bit Pi 5 (4 GB or 8 GB):
python3 -m pip install -r models/uuv/requirements-pi.txt
python3 models/uuv/infer.py --csv <telemetry>.csv --int8 --calibrate   # score + advisory flags
python3 models/uuv/pi_bench.py --int8                                   # confirm size/latency/RSS on-device
```
- **Advisory only:** the model *flags*; a human decides. Nothing is actioned automatically.
- The training stack (torch/sklearn) stays on **Node 3** (this Mac); only the ONNX + `infer.py`
  cross to the Pi. Pi provisioning itself is the William/Juan lane.

---

## 7. End-to-end data flow

```
BlueROV2/ArduSub logs (real, CC BY 4.0)
   │  ingest/ardusub.py  (align 10 Hz, 23 onboard channels)
   ▼
ingest/out/ardusub.csv  ──► windows (23×64) ──► standardize (scaler.json)
   │                                                  │
   │  train on NOMINAL only                           │  at runtime
   ▼                                                  ▼
Conv1d autoencoder  ──train──► model.pt ──export──► uuv_seq_ae(_int8).onnx
   │                                                  │
   │                                                  ▼
   │                                         score = mean((recon − x)²)
   │                                                  │
   │                                         in-situ threshold → advisory flag
   ▼
register in MLflow as `theseus-uuv` (fleet/mlflow_registry.py)
   │
   ▼
fleet flywheel: provenance-gated, eval-gated merge across UUV nodes (Node 3 coordinates)
```

---

## 8. How it plugs into the larger system

- **Registry:** the trainer registers the ONNX artifact + metrics as **`theseus-uuv`** through
  `fleet/mlflow_registry.py` — MLflow-optional (a no-op if no server), model-agnostic. The moment a
  Node-3 MLflow server is reachable, the model flows into the fleet flywheel with **no code change**.
- **Fleet learning:** once registered, the fleet brain can coordinate model deltas across UUV nodes
  (learn-local → sign → provenance-gate → eval-gate → merge), and every step is sealed in the
  tamper-evident record. This model is the **Framing-B anchor** (`UUV_FLEET_ARCHITECTURE.md`) — the
  "own-systems" counterpart to the Framing-A AIS detectors.
- **Edge serving** (`serve/`) is the Pi-side runtime; per the topology, Node 3 (this machine)
  trains/registers, the Pis run inference. Pi-side provisioning is the William/Juan lane.
- **Live edge receiver compatibility** (`serve/receiver/`): the system's streaming receiver
  (`receiver.py`) loads a model from MLflow (`models:/<name>@production`) and calls the River
  online interface — `score_one(record)` / `learn_one(record)` — one record at a time.
  `serve/receiver/uuv_seq_ae.py` adapts this model to that interface: `SequenceAEAdapter` **buffers
  per-record dicts into the sliding 64-sample window** and returns the reconstruction-error score
  once full (`learn_one` is a deliberate no-op — the AE is frozen). `register_uuv_seq_ae.py`
  registers it as **`theseus_uuv_deploy`** + a `@production` alias (a receiver-compatible pyfunc,
  distinct from the raw-artifact `theseus-uuv` fleet entry), with `config-uuv.yml` + a `uuv_ardusub`
  topic in `features.json` selecting the 23 channels. The adapter's `score_one`/`learn_one` interface
  and `.river_model`/`.model` lookup match the receiver exactly (verified streaming real records).
  **Caveat (MLflow 3.x):** the current `receiver.py` builds `models:/{name}/{version}` with the default
  `version="production"` — the *removed legacy stage* form, which does **not** resolve the `@production`
  alias, so it silently falls back to a baseline HST (this affects the team's `uuv1_anomaly_deploy`
  too). Fix: load `models:/{name}@production` (alias), or pin `version` to the registered number in
  config. Also: the receiver's shadow-model A/B is River-specific and not meaningful against a frozen AE.

---

## 9. Mental model in one paragraph

It's a "muscle memory for healthy" detector. The autoencoder builds muscle memory of what a healthy
UUV's battery, thrusters, attitude, IMU, and pressure look like over any 6-second stretch. Ask it to
re-draw a stretch it's watching: if it can re-draw it accurately, things are normal; if its re-draw
is far off, the vehicle is doing something it never learned as healthy — raise an advisory flag, and
let the watchstander decide. No fault catalogue required, calibrated to each vehicle's own baseline,
small enough to run on a Pi.

---

## Files

| File | Role |
|---|---|
| `ingest/ardusub.py` | logs → aligned 23-channel 10 Hz telemetry CSV |
| `models/uuv/train_uuv_ae.py` | model definition + training + scoring + ONNX-int8 export + MLflow register |
| `models/uuv/test_uuv_ae.py` | independent test harness (per-recording AUC, severity sweep, baselines) |
| **`models/uuv/infer.py`** | **torch-free edge serving** (numpy + onnxruntime only) — the deployable Pi runtime |
| `models/uuv/pi_bench.py` | inference-only Pi footprint (size / latency / RSS, platform-aware) |
| `models/uuv/requirements-pi.txt` | minimal Pi inference deps (`numpy` + `onnxruntime`) |
| `models/uuv/scaler.json` | channel order, per-channel mean/std, window, shipped threshold |
| `models/uuv/{model.pt, meta.json, results.json}` | weights, architecture/params, eval results |
| `models/onnx/uuv_seq_ae{,_int8}.onnx` | the deployable edge artifacts |
