# THESEUS edge inference server — CPU-only, Raspberry-Pi-realistic OCI image.
# =============================================================================
# Serves the promoted model from demo/models/current/ over HTTP and accepts
# shore→ship hot-swaps (POST /reload), sealing each swap into the tamper-evident
# record. NO GPU, NO CUDA — stdlib http.server, plus scikit-learn ONLY to unpickle
# sklearn-framework models (the stdlib-ols fallback needs nothing extra).
#
# Multi-arch: linux/arm64 builds run as-is on a Raspberry Pi 5 (aarch64).
#   docker buildx build --platform linux/arm64 -f serve/Dockerfile -t theseus-serve:0.1.0 .
#   docker build -f serve/Dockerfile -t theseus-serve:0.1.0 .     # local arch
#   (build from the REPO ROOT so serve/ demo/ referee/ are in context)
#
# Used by deploy/child-node-compose/model-serv.yml.
# =============================================================================

FROM python:3.14-slim

LABEL org.opencontainers.image.title="theseus-serve" \
      org.opencontainers.image.description="THESEUS edge inference server (CPU-only, CBM gas-turbine regressor) with shore→ship hot-swap sealed into the tamper-evident record." \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/joshsarles/theseus"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    EDGE_HOST=0.0.0.0 \
    EDGE_PORT=8080 \
    MODEL_DIR=/models/current \
    RECORD_DIR=/record

# scikit-learn only (CPU wheels exist for arm64). The stdlib-ols model path needs
# nothing beyond Python. mlflow is OPTIONAL (only touched when MLFLOW_TRACKING_URI
# is set) and kept out of the default image to stay RAM/disk-light on a 4GB Pi.
# Pin to the family the shore trainer uses (demo/retrain.py) so a model pickled on
# shore unpickles cleanly on the edge — version skew triggers sklearn warnings.
ARG SKLEARN_VERSION=">=1.7,<1.9"
ARG WITH_MLFLOW="0"
# hadolint ignore=DL3013,DL3042
RUN python3 -m pip install --no-cache-dir "scikit-learn==${SKLEARN_VERSION}" \
    && if [ "${WITH_MLFLOW}" = "1" ]; then python3 -m pip install --no-cache-dir "mlflow>=3.0,<4"; fi \
    && python3 -c "import sklearn; print('sklearn', sklearn.__version__)"

# serve/ needs demo/_record.py + referee/chain.py at the SAME relative layout the
# sealing code expects (demo/_record.py walks parents[1] to import referee.chain).
WORKDIR /opt/theseus
COPY serve/   /opt/theseus/serve/
COPY demo/_record.py /opt/theseus/demo/_record.py
COPY referee/ /opt/theseus/referee/

RUN rm -rf /opt/theseus/serve/__pycache__ /opt/theseus/serve/edge_inbox* \
           /opt/theseus/referee/__pycache__ \
    && mkdir -p /models /record \
    && chmod 0777 /record

# Unprivileged uid; the model dir is mounted read-only, the record dir read-write.
USER 65534:65534

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3).status==200 else 1)"

ENTRYPOINT ["python3", "/opt/theseus/serve/model_server.py"]
