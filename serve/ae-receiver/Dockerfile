FROM python:3.12-slim

# ---- system deps (slim base has no build tools needed for these wheels) ----
RUN pip install --no-cache-dir \
    numpy \
    onnxruntime \
    fastapi \
    "uvicorn[standard]"

# ---- application code ----
WORKDIR /app
COPY ae_receiver.py /app/ae_receiver.py

# ---- model assets baked in for standalone operation ----
# Mount override: docker run -v /your/models:/model to use a different version.
COPY model/uuv_seq_ae.onnx   /model/uuv_seq_ae.onnx
COPY model/scaler.json        /model/scaler.json
COPY model/results.json       /model/results.json

# ---- runtime ----
EXPOSE 54321
ENTRYPOINT ["uvicorn", "ae_receiver:app", "--host", "0.0.0.0", "--port", "54321"]
