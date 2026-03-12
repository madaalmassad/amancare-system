import os
import time
import math
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# =========================================================
# Load ENV
# =========================================================
load_dotenv(dotenv_path=".env")
import os
import requests

def send_whatsapp_alert(message_text: str):
    url = os.getenv("WATI_URL")
    api_key = os.getenv("9735be70e03c2ce866f462a232e33496")
    phone = os.getenv("966500137325")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "phone": phone,
        "messageText": message_text
    }

    rsponse = requests.post(url, json=payload, headers=headers)

    print(response.status_code)
    print(response.text)
    
    send_whatsapp_alert(
"""🚨 AmanCare Alert

Patient: Mohammed Alajmi
Status: Outside Safe Zone
Location detected outside safe zone

Immediate attention required"""
)

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print("WhatsApp status:", r.status_code, r.text)
    except Exception as e:
        print("WhatsApp error:", e)

APP_NAME = os.getenv("APP_NAME", "AmanCare")

# Session/Login
SECRET_KEY = os.getenv("SESSION_SECRET", "change-me-please")

# Safe Zone
SAFE_CENTER_LAT = float(os.getenv("SAFE_CENTER_LAT", "24.774265"))
SAFE_CENTER_LON = float(os.getenv("SAFE_CENTER_LON", "46.738586"))
SAFE_RADIUS_KM = float(os.getenv("SAFE_RADIUS_KM", "1.0"))
DEFAULT_DEVICE_ID = os.getenv("DEVICE_ID", "chip1")

# Simple admin credentials (for demo)
USERS = {
    "P1001": {"username": "admin", "password": "1234567"},
    "P1002": {"username": "doctor", "password": "1234567"}
}

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_COOLDOWN_SEC = int(os.getenv("ALERT_COOLDOWN_SEC", "60"))

# DB
DB_PATH = os.getenv("DB_PATH", "amancare.db")

# Device Auth Key (single key demo)
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
HMAC_SECRET = os.getenv("HMAC_SECRET", "")
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))

# Integrity (SHA-256) secret salt (optional but recommended)
SHA256_SALT = os.getenv("SHA256_SALT", "amancare_salt_2026")

# Rate limit (simple)
RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "10"))
RATE_LIMIT_MAX_REQ = int(os.getenv("RATE_LIMIT_MAX_REQ", "30"))

# =========================================================
# App init
# =========================================================
app = FastAPI()
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# =========================================================
# In-memory helpers
# =========================================================
_last_alert_ts: Dict[str, float] = {}          # device_id -> unix time
_last_alert_status: Dict[str, str] = {}        # device_id -> "SAFE"/"ALERT"
_rate_bucket: Dict[str, list] = {}             # ip -> [timestamps]

# Patient (demo)
PATIENT = {
    "name": os.getenv("PATIENT_NAME", "Mohammed Alajmi"),
    "age": int(os.getenv("PATIENT_AGE", "85")),
    "blood": os.getenv("PATIENT_BLOOD", "O+"),
    "phone": os.getenv("PATIENT_PHONE", "0551237841"),
    "emergency": os.getenv("PATIENT_EMERGENCY", "05547821639"),
}

# =========================================================
# DB functions
# =========================================================
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        status TEXT NOT NULL,
        distance_km REAL NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_device_id ON telemetry(device_id)")
    conn.commit()
    conn.close()

@app.on_event("startup")
def on_startup():
    init_db()

# =========================================================
# Security helpers
# =========================================================
def require_login(request: Request) -> bool:
    return bool(request.session.get("logged_in"))

def verify_device_key(request: Request) -> None:
    provided = request.headers.get("X-DEVICE-KEY", "")
    if not provided or provided != DEVICE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid device key")
    
def calc_payload_sha256(device_id: str, lat: float, lon: float, ts: str) -> str:
    msg = f"{device_id}|{lat:.6f}|{lon:.6f}|{ts}|{SHA256_SALT}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()

def verify_payload_sha256(request: Request, device_id: str, lat: float, lon: float, ts: str) -> None:
    provided_hash = request.headers.get("X-PAYLOAD-SHA256", "")
    expected_hash = calc_payload_sha256(device_id, lat, lon, ts)

    if not provided_hash or provided_hash != expected_hash:
        raise HTTPException(status_code=400, detail="Invalid SHA-256 (payload tampered)")

def rate_limit_or_429(ip: str) -> None:
    now = time.time()
    bucket = _rate_bucket.get(ip, [])
    # keep only window
    bucket = [t for t in bucket if now - t <= RATE_LIMIT_WINDOW_SEC]
    if len(bucket) >= RATE_LIMIT_MAX_REQ:
        raise HTTPException(status_code=429, detail="Too many requests")
    bucket.append(now)
    _rate_bucket[ip] = bucket

# =========================================================
# Geo helpers
# =========================================================
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d1 = math.radians(lat2 - lat1)
    d2 = math.radians(lon2 - lon1)
    a = (math.sin(d1 / 2) ** 2) + math.cos(p1) * math.cos(p2) * (math.sin(d2 / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

def compute_status_and_distance(lat: float, lon: float) -> (str, float):
    dist = haversine_km(lat, lon, SAFE_CENTER_LAT, SAFE_CENTER_LON)
    status = "ALERT" if dist > SAFE_RADIUS_KM else "SAFE"
    return status, dist

# =========================================================
# Telegram
# =========================================================
def telegram_send(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=8)
    except Exception:
        pass

def send_alert_if_needed(device_id: str, status: str) -> None:
    """
    Send telegram only on SAFE -> ALERT transition + cooldown
    """
    if status != "ALERT":
        _last_alert_status[device_id] = status
        return

    last_status = _last_alert_status.get(device_id, "SAFE")
    if last_status == "ALERT":
        return

    now = time.time()
    last_ts = _last_alert_ts.get(device_id, 0)
    if now - last_ts < ALERT_COOLDOWN_SEC:
        return

    _last_alert_ts[device_id] = now
    _last_alert_status[device_id] = status

    telegram_send(
        f"🚨 تنبيه {APP_NAME}\n"
        f"المريض: {PATIENT['name']}\n"
        f"الحالة: خارج منطقة الأمان\n"
        f"Device: {device_id}"
    )

# =========================================================
# Pages (Login / Dashboard)
# =========================================================
@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    patient_id: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    user = USERS.get(patient_id)

    if user and user["username"] == username and user["password"] == password:
        request.session["logged_in"] = True
        request.session["patient_id"] = patient_id
        return RedirectResponse("/dashboard", status_code=302)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid Patient ID or credentials"}
    )

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not require_login(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "patient": PATIENT,
        "device_id": DEFAULT_DEVICE_ID,
        "safe_center_lat": SAFE_CENTER_LAT,
        "safe_center_lon": SAFE_CENTER_LON,
        "safe_radius_km": SAFE_RADIUS_KM,
    })

# =========================================================
# Telemetry API (POST from chip/simulator)
# Requirements covered:
#  - Auth: X-DEVICE-KEY
#  - Integrity: X-PAYLOAD-SHA256
#  - DB: SQLite insert
#  - Status: SAFE/ALERT
# =========================================================
@app.post("/telemetry")
async def post_telemetry(request: Request):
    ip = request.client.host if request.client else "unknown"
    rate_limit_or_429(ip)

    verify_device_key(request)

    body = await request.json()
    device_id = body.get("device_id", DEFAULT_DEVICE_ID)

    try:
        lat = float(body.get("lat"))
        lon = float(body.get("lon"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lat/lon")

    # ts: allow provided, else server time ISO
    ts = body.get("ts")
    if not ts:
        ts = datetime.now(timezone.utc).isoformat()

    # Integrity check
    verify_payload_sha256(request, device_id, lat, lon, ts)

    status, dist = compute_status_and_distance(lat, lon)

    # Store in DB
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO telemetry (device_id, lat, lon, status, distance_km, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (device_id, lat, lon, status, float(dist), ts)
    )
    conn.commit()
    conn.close()

    # Alert on SAFE->ALERT
    send_alert_if_needed(device_id, status)

    return {
        "ok": True,
        "device_id": device_id,
        "status": status,
        "distance_km": round(dist, 3),
        "ts": ts
    }

# =========================================================
# Telemetry latest (GET)
# =========================================================
@app.get("/telemetry/latest")
def telemetry_latest(device_id: str = DEFAULT_DEVICE_ID):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT device_id, lat, lon, status, distance_km, created_at
        FROM telemetry
        WHERE device_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (device_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return JSONResponse({
            "device_id": device_id,
            "status": "SAFE",
            "lat": None,
            "lon": None,
            "distance_km": None,
            "ts": None
        })

    return {
        "device_id": row["device_id"],
        "status": row["status"],
        "lat": row["lat"],
        "lon": row["lon"],
        "distance_km": round(float(row["distance_km"]), 3),
        "ts": row["created_at"],
    }

# =========================================================
# Optional: health check
# =========================================================
@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME}
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    patient = {
        "name": "Mohammed Alajmi",
        "age": 85,
        "blood": "O+",
        "phone": "+966 55 481 2397",
        "guardian_phone": "+966 54 762 1843",
        "status": "SAFE",
        "distance": "63 m داخل النطاق الآمن"
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "patient": patient
        }
    )