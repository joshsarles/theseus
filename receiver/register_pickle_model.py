import pickle
import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
import pandas as pd

RUN_ID = "af0e990b943549838e52b5af58335ec1"
PKL_ARTIFACT_PATH = "model-UUV1-all.pkl"
REGISTERED_MODEL_NAME = "uuv1_anomaly_deploy"

class RiverAnomalyWrapper(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        with open(context.artifacts["river_pkl"], "rb") as f:
            self.model = pickle.load(f)

    def predict(self, context, model_input):
        if isinstance(model_input, pd.DataFrame):
            records = model_input.to_dict(orient="records")
        else:
            records = model_input
        return [self.model.score_one(x) for x in records]

mlflow.set_tracking_uri("http://localhost:5000")

model_uri = f"runs:/{RUN_ID}/{PKL_ARTIFACT_PATH}"

with mlflow.start_run(run_name="register-UUV1-all-pyfunc"):
    mlflow.pyfunc.log_model(
        artifact_path="river_pyfunc_model",
        python_model=RiverAnomalyWrapper(),
        artifacts={"river_pkl": model_uri},
        registered_model_name=REGISTERED_MODEL_NAME,
    )

client = MlflowClient()
latest = client.get_latest_versions(REGISTERED_MODEL_NAME)[-1]

client.transition_model_version_stage(
    name=REGISTERED_MODEL_NAME,
    version=latest.version,
    stage="Production",
    archive_existing_versions=True,
)

print(f"Registered {REGISTERED_MODEL_NAME} version {latest.version} as Production")