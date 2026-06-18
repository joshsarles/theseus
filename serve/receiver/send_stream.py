import json
import time
import requests
from pathlib import Path

URL = "http://127.0.0.1:8000/stream-item"
INPUT_FILE = Path("uuv1-all-anom.json")
TOPIC_ID = "all"
BATCH_SIZE = 25
INPUT_FILE = Path("uuv1-sensors-anom.json")

print(f"Reading: {INPUT_FILE.resolve()}")
records = json.loads(INPUT_FILE.read_text())
print(f"Loaded {len(records)} records")

for i in range(0, len(records), BATCH_SIZE):
    batch = records[i:i + BATCH_SIZE]
    payload = {"topic_id": TOPIC_ID, "data": batch}

    print(f"Sending batch {i // BATCH_SIZE + 1} with {len(batch)} records...")
    response = requests.post(URL, json=payload, timeout=10)
    print(response.status_code, response.text)

    time.sleep(1)

print("Done")