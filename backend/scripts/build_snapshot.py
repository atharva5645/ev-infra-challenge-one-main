"""
Fetch and compile a rich offline snapshot from the BEE Charging Station API.
Includes states, meta, operators, connectors, district directories, and
geocoded station records for offline demo reliability.
"""
import json
import time
from pathlib import Path
import httpx

BASE_URL = "https://ev-charging-stations-api.vercel.app"
OUT_FILE = Path(__file__).parent.parent / "app" / "data" / "bee_snapshot.json"
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

client = httpx.Client(base_url=BASE_URL, timeout=15.0)

print("Fetching metadata...")
meta = client.get("/v1/meta").json()
time.sleep(0.5)

print("Fetching states...")
states = client.get("/v1/states").json()
time.sleep(0.5)

print("Fetching connectors...")
connectors = client.get("/v1/connectors").json()
time.sleep(0.5)

print("Fetching operators...")
operators = client.get("/v1/operators").json()
time.sleep(0.5)

# Target key states covering all major corridors and high-density EV regions
priority_states = [
    "Karnataka", "Maharashtra", "Delhi", "Uttar Pradesh", "Tamil Nadu",
    "Telangana", "Gujarat", "Rajasthan", "Kerala", "West Bengal",
    "Haryana", "Punjab", "Andhra Pradesh", "Madhya Pradesh", "Puducherry"
]

cities_by_state = {}
for state_name in priority_states:
    print(f"Fetching cities for {state_name}...")
    try:
        res = client.get("/v1/cities", params={"state": state_name})
        if res.status_code == 200:
            cities_by_state[state_name] = res.json().get("data", [])
    except Exception as e:
        print(f"Failed cities for {state_name}: {e}")
    time.sleep(0.3)

stations = []
for state_name in priority_states:
    print(f"Fetching stations for {state_name}...")
    try:
        res = client.get("/v1/stations", params={"state": state_name, "limit": 100})
        if res.status_code == 200:
            records = res.json().get("data", [])
            print(f"  Got {len(records)} stations for {state_name}")
            stations.extend(records)
    except Exception as e:
        print(f"Failed stations for {state_name}: {e}")
    time.sleep(0.3)

snapshot = {
    "source": "Bureau of Energy Efficiency (BEE), Ministry of Power, Government of India",
    "snapshot_date": "2025-10-26",
    "attribution": meta.get("data", {}).get("attribution", ""),
    "meta": meta.get("data", {}),
    "states": states.get("data", []),
    "connectors": connectors.get("data", []),
    "operators": operators.get("data", []),
    "cities_by_state": cities_by_state,
    "stations": stations,
}

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)

print(f"Successfully saved snapshot to {OUT_FILE} with {len(stations)} stations across {len(priority_states)} states!")

