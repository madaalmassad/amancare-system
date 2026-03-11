import os
import time
import math
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env
load_dotenv(dotenv_path=".env")

# =========================
# Config (from .env)
# =========================
BASE_URL = os.getenv("BASE_URL", "https://127.0.0.1:8000").rstrip("/")
DEVICE_ID = os.getenv("DEVICE_ID", "chip1")

# Your server expects this header for device authentication
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", os.getenv("DEVICE_KEY", "amancare_device_key_2026"))

# Must match main.py SHA256_SALT exactly
SHA256_SALT = os.getenv("SHA256_SALT", "amancare_hmac_secret_2026")

SAFE_CENTER_LAT = float(os.getenv("SAFE_CENTER_LAT", "24.7016"))
SAFE_CENTER_LON = float(os.getenv("SAFE_CENTER_LON", "46.6873"))

# Movement simulation
STEP = float(os.getenv("SIM_STEP", "0.35"))          # how much to move each iteration
SLEEP_SEC = float(os.getenv("SIM_SLEEP_SEC", "2"))   # delay between posts

POST_PATH = "/telemetry"


# =========================
# Helpers
# =========================
def calc_payload_sha256(device_id: str, lat: float, lon: float, ts: str) -> str:
    """
    MUST match server canonical format exactly:
      device_id|lat(6dp)|lon(6dp)|ts|SHA256_SALT
    """
    msg = f"{device_id}|{lat:.6f}|{lon:.6f}|{ts}|{SHA256_SALT}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()

def send_once(lat: float, lon: float):

    ts = datetime.utcnow().isoformat()

    payload = {
        "device_id": DEVICE_ID,
        "lat": lat,
        "lon": lon,
        "ts": ts
    }

    provided_hash = calc_payload_sha256(DEVICE_ID, lat, lon, ts)

    headers = {
        "X-DEVICE-KEY": DEVICE_API_KEY,
        "X-PAYLOAD-SHA256": provided_hash
    }

    url = f"{BASE_URL}{POST_PATH}"

    try:
        r = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10,
            verify=False
        )
        print("POST", r.status_code, r.text)

    except Exception as e:
        print("ERR", e)

    # start at safe center then move away gradually
def main():
    # start at safe center then move away gradually
    lat = SAFE_CENTER_LAT
    lon = SAFE_CENTER_LON
    t = 0.0

    while True:
        lat2 = lat + math.sin(t) * 0.0001
        lon2 = lon + math.cos(t) * 0.0001

        send_once(lat2, lon2)

        t += 0.3
        time.sleep(2)


if __name__ == "__main__":
    main()