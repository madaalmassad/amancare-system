# ============================
# IMPORTS
# ============================
import os
import math
import random
import sqlite3
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from twilio.rest import Client


# ============================
# APP SETUP
# ============================
app = FastAPI()
app.state.last_alert_sent = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.add_middleware(SessionMiddleware, secret_key="secret123")


# ============================
# ROOT
# ============================
@app.get("/")
def root():
    return RedirectResponse("/login")


# ============================
# TWILIO
# ============================
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(account_sid, auth_token) if account_sid and auth_token else None


def send_whatsapp(msg):
    if not client:
        return
    client.messages.create(
        from_="whatsapp:+14155238886",
        body=msg,
        to="whatsapp:+966XXXXXXXXX"
    )


# ============================
# DATABASE
# ============================
DB_PATH = os.path.join(BASE_DIR, "amancare.db")


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        lat REAL,
        lon REAL,
        status TEXT,
        distance_km REAL,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ============================
# DATA
# ============================
settings = {
    "safe_lat": 24.7136,
    "safe_lon": 46.6753,
    "safe_radius": 0.2
}

PATIENT = {
    "name": "Mohammed Alajmi",
    "gender": "Male",
    "age": 85,
    "blood": "O+",
    "diagnosis": "Alzheimer's Disease"
}

USERS = {
    "P1001": {"username": "admin", "password": "1234567", "role": "admin"},
    "P1002": {"username": "doctor", "password": "1234567", "role": "doctor"}
}


# ============================
# HELPERS
# ============================
def require_login(request):
    return request.session.get("logged_in")


def require_role(request, roles):
    return request.session.get("role") in roles


# ============================
# LOGIN
# ============================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login_post(request: Request, patient_id: str = Form(...), username: str = Form(...), password: str = Form(...)):
    user = USERS.get(patient_id)

    if user and user["username"] == username and user["password"] == password:
        request.session["otp"] = str(random.randint(1000, 9999))
        request.session["role"] = user["role"]
        return RedirectResponse("/verify-otp", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request, "error": "Wrong login"})


# ============================
# OTP
# ============================
@app.get("/verify-otp", response_class=HTMLResponse)
def otp_page(request: Request):
    return templates.TemplateResponse("verify_otp.html", {"request": request})


@app.post("/verify-otp", response_class=HTMLResponse)
def otp_post(request: Request, otp: str = Form(...)):
    if otp == request.session.get("otp"):
        request.session["logged_in"] = True
        return RedirectResponse("/dashboard", status_code=302)

    return templates.TemplateResponse("verify_otp.html", {"request": request, "error": "Wrong OTP"})


# ============================
# DASHBOARD
# ============================
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not require_login(request):
        return RedirectResponse("/login")

    return templates.TemplateResponse("overview.html", {"request": request, "patient": PATIENT})


# ============================
# MEDICAL
# ============================
@app.get("/medical-profile", response_class=HTMLResponse)
def medical(request: Request):
    return templates.TemplateResponse("medical_profile.html", {"request": request, "patient": PATIENT})


# ============================
# LIVE MONITOR
# ============================
@app.get("/live-monitoring", response_class=HTMLResponse)
def live(request: Request):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT lat, lon, status FROM telemetry ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    return templates.TemplateResponse("live_monitoring.html", {"request": request, "data": row})


# ============================
# LOCATION CONTROL
# ============================
@app.get("/location-control", response_class=HTMLResponse)
def location(request: Request):
    return templates.TemplateResponse("location_control.html", {"request": request})


# ============================
# TELEMETRY
# ============================
@app.post("/telemetry")
async def telemetry(data: dict):
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))

    dist = ((lat - settings["safe_lat"]) ** 2 + (lon - settings["safe_lon"]) ** 2) ** 0.5 * 111

    status = "SAFE" if dist <= settings["safe_radius"] else "ALERT"

    if status == "ALERT" and not app.state.last_alert_sent:
        send_whatsapp("🚨 ALERT: Patient خارج المنطقة")
        app.state.last_alert_sent = True

    if status == "SAFE":
        app.state.last_alert_sent = False

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO telemetry (device_id, lat, lon, status, distance_km, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("chip1", lat, lon, status, dist, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()

    return {"ok": True}