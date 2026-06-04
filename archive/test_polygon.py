from dotenv import load_dotenv
load_dotenv()
import os
import json
from datetime import datetime, timedelta
import requests

ENV_PATH = ".env"

def get_polygon_key():
    k = os.getenv("POLYGON_API_KEY", "").strip()
    if not k and os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and line.startswith("POLYGON_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return k

key = get_polygon_key()
if not key:
    raise SystemExit("POLYGON_API_KEY not found. Add it to .env.")

# Quick sanity print (masked)
print(f"Using POLYGON_API_KEY: {key[:4]}...{key[-4:]} (len={len(key)})")

symbol = "C:USDJPY"      # Forex symbol format on Polygon
multiplier = 1
timespan = "day"         # change to "hour" to test intraday
end = datetime.utcnow().date().isoformat()
start = (datetime.utcnow().date() - timedelta(days=3)).isoformat()

url = (
    f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/"
    f"{multiplier}/{timespan}/{start}/{end}"
    f"?adjusted=true&sort=asc&limit=10&apiKey={key}"
)

print("Requesting:", url.split("apiKey=")[0] + "apiKey=***")

r = requests.get(url, timeout=20)
print("Status:", r.status_code)

try:
    data = r.json()
except Exception:
    print("Raw response:", r.text[:500])
    raise

print("Response:", {k: data.get(k) for k in ["status", "queryCount", "resultsCount", "error"]})
if isinstance(data, dict) and "results" in data:
    print("First result:", json.dumps(data["results"][0], indent=2))
