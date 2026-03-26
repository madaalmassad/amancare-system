import os
import time
import math
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================
# Load .env
# =========================
load_dotenv(dotenv_path=".env")

# =========================
# Config
# =========================
BASE_URL = "https://amancare-system-94wm.onrender.com"
DEVICE_ID = os.getenv("DEVICE_ID", "chip1")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "amancare_device_key_2026")
SHA256_SALT = os.getenv("SHA256_SALT", "amancare_hmac_secret_2026")

POST_PATH = "/telemetry"
SAFE_ZONE_API = "/api/safe-zone"

SLEEP_SEC = 2


# =========================
# SHA256 (security)
# =========================
def calc_payload_sha256(device_id: str, lat: float, lon: float, ts: str) -> str:
    msg = f"{device_id}|{lat:.6f}|{lon:.6f}|{ts}|{SHA256_SALT}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


# =========================
# Send telemetry
# =========================
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


# =========================
# Get safe zone from server
# =========================
def get_safe_zone():
    url = f"{BASE_URL}{SAFE_ZONE_API}"
    try:
        r = requests.get(url, timeout=10, verify=False)
        data = r.json()
        return float(data["lat"]), float(data["lon"]), float(data["radius"])
    except Exception as e:
        print("SAFE_ZONE_ERR", e)
        return 24.7136, 46.6753, 0.2


# =========================
# Main loop
# =========================
def main():
    t = 0.0

    while True:
        safe_lat, safe_lon, safe_radius = get_safe_zone()

        # يتحرك أحيانًا داخل وأحيانًا خارج السيف زون
        movement_factor = 1.5 if math.sin(t) > 0 else 0.5
        offset = (safe_radius / 111.0) * movement_factor

        lat = safe_lat + math.sin(t) * offset
        lon = safe_lon + math.cos(t) * offset

        send_once(lat, lon)

        t += 0.4
        time.sleep(SLEEP_SEC)


if __name__ == "__main__":
    main()