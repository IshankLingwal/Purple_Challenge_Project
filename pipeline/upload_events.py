import json
import requests

with open("events.jsonl", "r", encoding="utf-8") as f:
    events = [json.loads(line) for line in f]

payload = {
    "events": events
}

response = requests.post(
    "http://localhost:8000/events/ingest",
    json=payload
)

print("Status Code:", response.status_code)
print("Response:", response.json())