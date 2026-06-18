FROM analytics-base:latest

USER 1001
COPY --chmod=0755 receiver.py .
COPY --chmod=0644 config.yml .
COPY --chmod=0644 features.json .

ENTRYPOINT ["uvicorn", "receiver:app", "--host", "0.0.0.0"]
CMD ["--port", "54321", "--workers", "1"]