import os
import json
import yaml
import asyncio
from collections import deque
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

import mlflow
import mlflow.pyfunc
from river import anomaly

app = FastAPI(title="UUV Edge Receiver")

# --- 1. CONFIGURATION ---
CONFIG_FILE = os.getenv("RECEIVER_CONFIG", "config.yml")
FEATURE_FILE = os.getenv("FEATURE_FILE", "features.json")
TIMESTAMP_FIELD = "timestamp_utc"

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

stream_cfg = config.get("stream", {})
mlflow_cfg = config.get("mlflow", {})

TARGET_TOPIC_ID = stream_cfg.get("topic", "sensors")
BATCH_SIZE = int(stream_cfg.get("batch_size", 25))
HISTORY_SIZE = int(stream_cfg.get("history_size", 100))
ENABLE_MLFLOW_SYNC = bool(mlflow_cfg.get("sync_enabled", False))

MLFLOW_TRACKING_URI = (
    f"http://{mlflow_cfg.get('host', 'localhost')}:{mlflow_cfg.get('port', 5050)}"
)
MODEL_NAME = mlflow_cfg.get("model", "uuv1_anomaly_deploy")
EXPERIMENT_NAME = mlflow_cfg.get("experiment", "uuv1_anomaly_train")

with open(FEATURE_FILE, "r", encoding="utf-8") as f:
    feature_config = json.load(f)

if TARGET_TOPIC_ID not in feature_config:
    raise KeyError(
        f"features.json does not contain key '{TARGET_TOPIC_ID}'. "
        f"Available keys: {list(feature_config.keys())}"
    )

FEATURE_LIST = feature_config[TARGET_TOPIC_ID]

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(EXPERIMENT_NAME)

incoming_queue: asyncio.Queue = asyncio.Queue()
history_queue: asyncio.Queue = asyncio.Queue()
historical_records = deque(maxlen=HISTORY_SIZE)


# --- 2. JSON RIVER WRAPPER FOR MLFLOW ---
class JsonRiverHSTWrapper(mlflow.pyfunc.PythonModel):
    """
    MLflow pyfunc wrapper for a River HalfSpaceTrees model.

    Note: this stores only basic HalfSpaceTrees parameters/counter, not the full
    learned tree state. For exact model persistence, prefer pickle/joblib or a
    custom full-state serializer.
    """

    def __init__(self, river_model=None):
        self.river_model = river_model

    def load_context(self, context):
        json_file_path = os.path.join(context.artifacts["river_state_dir"], "river_state.json")
        with open(json_file_path, "r", encoding="utf-8") as f:
            model_state = json.load(f)

        self.river_model = anomaly.HalfSpaceTrees(
            n_trees=model_state.get("n_trees", 10),
            height=model_state.get("height", 8),
            window_size=model_state.get("window_size", 250),
            seed=model_state.get("seed", model_state.get("random_state", 42)),
        )
        if "_counter" in model_state:
            self.river_model._counter = model_state["_counter"]

    def predict(self, context, model_input):
        return [self.river_model.score_one(row) for row in model_input.to_dict(orient="records")]


def make_hst(n_trees=10, height=8, window_size=250, seed=42):
    return anomaly.HalfSpaceTrees(
        n_trees=n_trees,
        height=height,
        window_size=window_size,
        seed=seed,
    )


def load_production_model():
    """Pull current Production model from MLflow, or initialize a local baseline model."""
    try:
        model_uri = f"models:/{MODEL_NAME}/Production"
        print(f"Loading Production model from MLflow: {model_uri}")
        pyfunc_model = mlflow.pyfunc.load_model(model_uri)
        return pyfunc_model._model_impl.python_model.river_model
    except Exception as e:
        print(f"Could not pull Production model ({e}). Instantiating baseline River HST.")
        return make_hst(n_trees=10, height=8, window_size=250, seed=42)


active_model = load_production_model()
shadow_model = make_hst(n_trees=12, height=8, window_size=250, seed=42)

active_score_sum = 0.0
shadow_score_sum = 0.0
processed_count = 0


# --- 3. REQUEST VALIDATION SCHEMA ---
class IncomingRecord(BaseModel):
    topic_id: str
    data: List[Dict[str, Any]]


def get_model_state(model) -> Dict[str, Any]:
    return {
        "n_trees": getattr(model, "n_trees", None),
        "height": getattr(model, "height", None),
        "window_size": getattr(model, "window_size", None),
        "seed": getattr(model, "seed", 42),
        "_counter": getattr(model, "_counter", 0),
    }


def sync_log_to_mlflow(model_to_log, avg_score: float):
    """Log a candidate edge model to MLflow without promoting it."""
    if not ENABLE_MLFLOW_SYNC:
        print("MLflow sync disabled; candidate model was not uploaded.")
        return

    try:
        tmp_dir = Path("tmp_state")
        tmp_dir.mkdir(exist_ok=True)
        with open(tmp_dir / "river_state.json", "w", encoding="utf-8") as f:
            json.dump(get_model_state(model_to_log), f, indent=2)

        artifacts = {"river_state_dir": str(tmp_dir)}

        with mlflow.start_run() as run:
            mlflow.log_metric("avg_anomaly_score", avg_score)
            mlflow.log_param("serialization", "river_state_json")
            mlflow.log_param("source", "edge_receiver_candidate")

            wrapped_model = JsonRiverHSTWrapper(river_model=model_to_log)
            mlflow.pyfunc.log_model(
                artifact_path="secure_river_model",
                python_model=wrapped_model,
                artifacts=artifacts,
            )
            print(f"Logged candidate model to MLflow run {run.info.run_id}.")
    except Exception as e:
        print(f"Failed to log candidate model to MLflow: {e}")


# --- 4. BACKGROUND STREAMING WORKERS ---
async def streaming_pipeline_worker():
    global active_model, shadow_model, active_score_sum, shadow_score_sum, processed_count
    print("Streaming pipeline worker initialized.")

    while True:
        item: IncomingRecord = await incoming_queue.get()
        try:
            for record in item.data:
                x = {k: record[k] for k in FEATURE_LIST if k in record}
                missing = [k for k in FEATURE_LIST if k not in record]

                if not x:
                    await history_queue.put(
                        {
                            "topic_id": item.topic_id,
                            "timestamp_utc": record.get(TIMESTAMP_FIELD),
                            "error": "No configured features found in record.",
                            "missing_features": missing,
                        }
                    )
                    continue

                # Score before learning so the model does not immediately adapt to the same record.
                active_score = active_model.score_one(x)
                shadow_score = shadow_model.score_one(x)

                active_score_sum += active_score
                shadow_score_sum += shadow_score

                active_model.learn_one(x)
                shadow_model.learn_one(x)
                processed_count += 1

                await history_queue.put(
                    {
                        "topic_id": item.topic_id,
                        "timestamp_utc": record.get(TIMESTAMP_FIELD),
                        "features": x,
                        "missing_features": missing,
                        "active_anomaly_score": active_score,
                        "shadow_anomaly_score": shadow_score,
                    }
                )

                if processed_count >= BATCH_SIZE:
                    avg_active = active_score_sum / processed_count
                    avg_shadow = shadow_score_sum / processed_count

                    if avg_shadow > avg_active:
                        print("Shadow model scored higher than active model; logging candidate.")
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, sync_log_to_mlflow, shadow_model, avg_shadow)
                        shadow_model = make_hst(n_trees=12, height=9, window_size=250, seed=42)
                    else:
                        print("Active model preserved for this batch.")

                    active_score_sum = 0.0
                    shadow_score_sum = 0.0
                    processed_count = 0
        finally:
            incoming_queue.task_done()


async def history_buffer_worker():
    print("History buffer worker initialized.")
    while True:
        snapshot = await history_queue.get()
        historical_records.append(snapshot)
        history_queue.task_done()


# --- 5. APP LIFECYCLE ---
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(streaming_pipeline_worker())
    asyncio.create_task(history_buffer_worker())


# --- 6. ENDPOINTS ---
@app.post("/stream-item")
async def receive_item(item: IncomingRecord):
    if item.topic_id != TARGET_TOPIC_ID:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Gateway rejected payload. Expected '{TARGET_TOPIC_ID}', received '{item.topic_id}'.",
        )

    await incoming_queue.put(item)
    return {
        "status": "buffered",
        "records_received": len(item.data),
        "current_buffer_depth": incoming_queue.qsize(),
    }


@app.get("/history", response_model=List[Dict[str, Any]])
async def get_processing_history():
    return list(historical_records)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "target_topic": TARGET_TOPIC_ID,
        "batch_size": BATCH_SIZE,
        "history_size": HISTORY_SIZE,
        "feature_count": len(FEATURE_LIST),
        "mlflow_uri": MLFLOW_TRACKING_URI,
        "mlflow_sync_enabled": ENABLE_MLFLOW_SYNC,
    }
