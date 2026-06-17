import json
import glob

files = glob.glob("data/*.json")
for f in files[:3]:  # just first 3
    print(f"\n=== {f} ===")
    with open(f) as fh:
        data = json.load(fh)
    if isinstance(data, list):
        print(f"Array of {len(data)} records")
        print("First record keys:", list(data[0].keys()) if data else "empty")
    elif isinstance(data, dict):
        print("Dict keys:", list(data.keys()))