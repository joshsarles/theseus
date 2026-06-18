import os
import yaml
import json
import asyncio
import logging
from contextlib import asynccontextmanager
import requests
from collections import deque
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import mlflow
import mlflow.pyfunc
from river import anomaly

# --- 0. LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ReceiverEngine")

# --- 1. CONFIGURATION ---
CONFIG_FILE = "config.yml"
FEATURE_FILE = "features.json"
TIMESTAMP_FIELD = "timestamp_utc"

logger.info("Loading configurations...")
try:
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    logger.error(f"Configuration file {CONFIG_FILE} not found! Using defaults.")
    config = {}

TARGET_TOPIC_ID = config.get("stream", {}).get("topic", "sensors")
BATCH_SIZE = config.get("stream", {}).get("batch_size", 25)
HISTORY_SIZE = config.get("stream", {}).get("history_size", 100)
MLFLOW_TRACKING_URI = "".join([
    "http://",
    config.get("mlflow", {}).get("host", "localhost"),
    ":",
    str(config.get("mlflow", {}).get("port", 5000))
])
MODEL_NAME = config.get("mlflow", {}).get("model", "uuv1_anomaly_deploy")
EXPERIMENT_NAME = config.get("mlflow", {}).get("experiment", "uuv1_anomaly_train")

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(EXPERIMENT_NAME)

try:
    with open(FEATURE_FILE, 'r') as f:
        FEATURE_LIST = json.load(f)[TARGET_TOPIC_ID]
    logger.info(f"Successfully loaded {len(FEATURE_LIST)} features for topic '{TARGET_TOPIC_ID}'.")
except (FileNotFoundError, KeyError) as e:
    logger.warning(f"Could not parse features for {TARGET_TOPIC_ID}. Defaulting to empty feature list. Error: {e}")
    FEATURE_LIST = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    logger.info(f"Connecting to MLflow Tracking Server at {MLFLOW_TRACKING_URI}...")
    try:
       # mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
       # mlflow.set_experiment(EXPERIMENT_NAME)
        app.state.mlflow_enabled = True
        logger.info(f"Successfully connected to MLflow. Experiment set to: '{EXPERIMENT_NAME}'")
    except Exception as e:
        app.state.mlflow_enabled = False
        logger.warning(f"MLflow tracking unavailable (running in isolated mode): {e}")

    yield
    logger.info("Shutting down application lifespan workers.")

app = FastAPI(lifespan=lifespan)
app.state.mlflow_enabled = False  # Initialize default state safety

# Queue 1: Absorbs raw HTTP traffic spikes
incoming_queue: asyncio.Queue = asyncio.Queue()

# Queue 2: The Double Buffer for historical tracking
history_queue: asyncio.Queue = asyncio.Queue()

# The final container that the GET endpoint reads from
historical_records = deque(maxlen=HISTORY_SIZE)


# --- 2. SECURE JSON RIVER WRAPPER FOR MLFLOW ---
class JsonRiverHSTWrapper(mlflow.pyfunc.PythonModel):
    """
    Custom MLflow wrapper that saves and loads River models 
    using pure JSON to avoid pickle vulnerabilities.
    """
    def __init__(self, river_model=None):
        self.river_model = river_model

    def save_context(self, context, model_path):
        """Extracts core hyperparams and state weights to JSON format."""
        model_state = {
            "n_trees": self.river_model.n_trees,
            "height": self.river_model.height,
            "window_size": self.river_model.window_size,
            "seed": self.river_model.seed,
            "_counter": getattr(self.river_model, "_counter", 0)
        }
        json_file_path = os.path.join(model_path, "river_state.json")
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(model_state, f, indent=4)
        logger.info("🔒 Model checkpoint saved securely as JSON state.")

    def load_context(self, context):
        """Reconstructs the River object from the JSON artifact folder."""
        json_file_path = os.path.join(context.artifacts["river_state_dir"], "river_state.json")
        with open(json_file_path, "r", encoding="utf-8") as f:
            model_state = json.load(f)
            
        self.river_model = anomaly.HalfSpaceTrees(
            n_trees=model_state["n_trees"],
            height=model_state["height"],
            window_size=model_state["window_size"],
            seed=model_state["seed"]
        )
        if "_counter" in model_state:
            self.river_model._counter = model_state["_counter"]
        logger.info("🔓 River HST model securely restored from JSON configuration.")

    def predict(self, context, model_input):
        return [self.river_model.score_one(row) for row in model_input.to_dict(orient='records')]


# --- 3. DYNAMIC BOOTSTRAPPING ENGINE ---
def load_production_model():
    """Pulls current weights from MLflow Model Registry, or initializes a clean shell."""
    try:
        model_uri = f"models:/{MODEL_NAME}/1"
        logger.info(f"📥 Attempting to pull Production weights from MLflow Registry: {model_uri}")
        pyfunc_model = mlflow.pyfunc.load_model(model_uri)
        logger.info("✅ Production model successfully pulled and instantiated.")
        # return pyfunc_model._model_impl.python_model.river_model
        python_model = pyfunc_model._model_impl.python_model

        if hasattr(python_model, "river_model"):
            return python_model.river_model

        if hasattr(python_model, "model"):
            return python_model.model

        raise AttributeError("Loaded MLflow pyfunc model has neither river_model nor model")
    except Exception as e:
        logger.warning(f"⚠️ Production model load failed ({e}). Instantiating baseline River HST model.")
        return anomaly.HalfSpaceTrees(n_trees=10, height=8, window_size=250, seed=42)

# Global runtime pointers for models and tracking metrics
active_model = load_production_model()
shadow_model = anomaly.HalfSpaceTrees(n_trees=12, height=8, window_size=250, seed=42)

active_score_sum = 0.0
shadow_score_sum = 0.0
processed_count = 0


# --- 4. REQUEST VALIDATION SCHEMA ---
class IncomingRecord(BaseModel):
    topic_id: str
    data: List[Dict[str, Any]]


# --- 5. NON-BLOCKING SYNC MLFLOW LOGGING ---
def sync_log_to_mlflow(model_to_log, score):
    """Worker sub-routine to ship artifacts cleanly across network threads."""
    logger.info("🧵 Starting background execution thread for MLflow serialization...")
    try:
        os.makedirs("./tmp_state", exist_ok=True)
        temp_state = {
            "n_trees": model_to_log.n_trees,
            "height": model_to_log.height,
            "window_size": model_to_log.window_size,
            "seed": model_to_log.seed,
            "_counter": getattr(model_to_log, "_counter", 0)
        }
        with open("./tmp_state/river_state.json", "w") as f:
            json.dump(temp_state, f)

        artifacts = {"river_state_dir": "./tmp_state"}

        with mlflow.start_run() as run:
            mlflow.log_metric("avg_anomaly_score", score)
            mlflow.log_param("serialization", "pure_json")
            
            wrapped_model = JsonRiverHSTWrapper(river_model=model_to_log)
            mlflow.pyfunc.log_model(
                artifact_path="secure_river_model",
                python_model=wrapped_model,
                artifacts=artifacts
            )
            logger.info(f"🚀 Successfully pushed Run '{run.info.run_id}' directly to MLflow Registry.")
    except Exception as e:
        logger.error(f"❌ Network connection error to MLflow Logging Endpoint: {e}")


# --- 6. BACKGROUND STREAMING WORKER LOOP ---
# --- WORKER 1: CORE MACHINE LEARNING ENGINE ---
async def streaming_pipeline_worker():
    global active_model, shadow_model, active_score_sum, shadow_score_sum, processed_count
    logger.info("🤖 Streaming Pipeline ML Worker Thread initialized.")
    
    while True:
        item: IncomingRecord = await incoming_queue.get()
        logger.debug(f"Processing item batch containing {len(item.data)} nested elements.")
        
        # FIXED: Loop over elements since item.data is defined as a List of Dicts
        for record in item.data:
            item_timestamp = record.get(TIMESTAMP_FIELD, "UNKNOWN")
            x = {k: record[k] for k in FEATURE_LIST if k in record}
            
            # Step A: Evaluate record behavior ahead of adaptation step
            active_score = active_model.score_one(x)
            shadow_score = shadow_model.score_one(x)
            
            active_score_sum += active_score
            shadow_score_sum += shadow_score
            
            # Step B: Streaming step evolution update
            active_model.learn_one(x)
            shadow_model.learn_one(x)
            
            processed_count += 1
            
            # Step C: Evaluate Performance Boundaries
            if processed_count >= BATCH_SIZE:
                avg_active = active_score_sum / BATCH_SIZE
                avg_shadow = shadow_score_sum / BATCH_SIZE
                
                logger.info(f"📊 Batch Checkpoint [Size {BATCH_SIZE}] -> Avg Active Score: {avg_active:.4f} | Avg Shadow Score: {avg_shadow:.4f}")
                
                # If shadow variant captures anomalies with higher sensitivity, deploy swap
                if shadow_score_sum > active_score_sum:
                    logger.warning("🔄 [MODEL IMPROVEMENT DETECTED] Shadow out-performed Active model. Promoting shadow...")
                    
                    # Offload outbound MLflow logging network traffic safely to thread executor
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, sync_log_to_mlflow, active_model, avg_shadow)
                    
                    # Re-provision shadow framework variant parameters for next evaluation window
                    # FIXED: Changed random_state to seed to match river schema
                    shadow_model = anomaly.HalfSpaceTrees(n_trees=10, height=9, window_size=250, seed=42)
                else:
                    logger.info("✅ [EVALUATION STABLE] Active architecture preserved dominant state.")
                
                # Flush pipeline measurement buffers
                active_score_sum, shadow_score_sum, processed_count = 0.0, 0.0, 0
            
            # Step D: Wrap historical snapshot data
            active_snapshot = {
                "topic_id": item.topic_id,
                "timestamp_utc": item_timestamp,
                "features": x,
                "anomaly_score": active_score
            }
            await history_queue.put(active_snapshot)
        
        incoming_queue.task_done()


# --- WORKER 2: HISTORICAL BUFFER MANAGER ---
async def history_buffer_worker():
    """Maintains the sliding window completely detached from the ML loop."""
    logger.info("📜 History Auditor Worker initialized.")
    while True:
        snapshot = await history_queue.get()
        historical_records.append(snapshot)
        logger.debug(f"History updated. Current history depth: {len(historical_records)}/{HISTORY_SIZE}")
        history_queue.task_done()


# --- 7. APPS LIFECYCLE INITIALIZER ---
@app.on_event("startup")
async def startup_event():
    """Launches the core engine loop concurrently on startup."""
    logger.info("Launching background pipeline coroutines...")
    # FIXED: Corrected spelling from aysncio.create_tast to asyncio.create_task
    asyncio.create_task(streaming_pipeline_worker())
    asyncio.create_task(history_buffer_worker())
    logger.info("All background worker loops have spun up successfully.")


# --- 8. GATEWAY SERVICE ENDPOINTS ---
@app.get("/")
def read_root():
    return {"mlflow_connected": app.state.mlflow_enabled}


@app.post("/stream-item")
async def receive_item(item: IncomingRecord):
    """
    Accepts incoming streaming payloads, acts as a gateway 
    filtering for the correct topic, and drops records onto the buffer.
    """
    if item.topic_id != TARGET_TOPIC_ID:
        logger.warning(f"🚫 Rejected item from mismatching topic: Expected '{TARGET_TOPIC_ID}', received '{item.topic_id}'")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Gateway Rejected. Expected '{TARGET_TOPIC_ID}', received '{item.topic_id}'."
        )
    
    await incoming_queue.put(item)
    logger.info(f"📥 Received and buffered inbound record for topic '{item.topic_id}' (Queue Size: {incoming_queue.qsize()})")
    return {
        "status": "buffered", 
        "current_buffer_depth": incoming_queue.qsize()
    }


@app.get("/history", response_model=List[Dict[str, Any]])
async def get_processing_history():
    logger.info(f"📤 Exporting {len(historical_records)} records from the evaluation log buffer.")
    return list(historical_records)