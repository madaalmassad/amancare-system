
# ============================
# ===== IMPORTS =====
import os, math, sqlite3, hashlib
from datetime import datetime, timezone
from aiohttp import request

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from twilio.rest import Client

# ===== APP =====
app = FastAPI()
@app.get("/")
def home():
    return {"status": "AmanCare is running "}
app.state.last_alert_sent = False

import os
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)


def send_whatsapp(msg):
    message = client.messages.create(
        from_='whatsapp:+14155238886',
        body=msg,
        to='whatsapp:+966500137325'
    )

# ============================
# APP
# ============================
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key="secret123")

# DB
DB_PATH = "amancare.db"

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        username TEXT,
        role TEXT,
        details TEXT,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def log_event(event_type: str, username: str = "", role: str = "", details: str = ""):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audit_logs (event_type, username, role, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (event_type, username, role, details, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()


# ============================
# DATA
# ============================
settings = {
    "patient_lat": 24.7136,
    "patient_lon": 46.6753,
    "safe_lat": 24.7136,
    "safe_lon": 46.6753,
    "safe_radius": 0.2
}

PATIENT = {
    "name": "Mohammed Alajmi",
    "gender": "Male",
    "age": 85,
    "blood": "O+",
    "nationality": "Saudi",
    "id_number": "1023456789",
    "diagnosis": "Alzheimer's Disease",
    "phone": "0551237841",
    "guardian_phone": "0500137325",
    "status": "SAFE",
    "height": "170 cm",
    "weight": "72 kg",
    "allergies": "Penicillin",
    "diseases": "Diabetes"
}

USERS = {
    "P1001": {
        "username": "admin",
        "password": "1234567",
        "role": "admin"
    },
    "P1002": {
        "username": "doctor",
        "password": "1234567",
        "role": "doctor"
    }
}
# ============================
# HELPERS
# ============================
def require_login(request: Request):
    if not request.session.get("logged_in"):
        return False
    return True

def require_role(request: Request, allowed_roles: list[str]) -> bool:
    if not request.session.get("logged_in"):
        return False
    user_role = request.session.get("role")
    return user_role in allowed_roles

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def get_status(lat, lon):
    dist = haversine(lat, lon, settings["safe_lat"], settings["safe_lon"])
    return ("ALERT" if dist > settings["safe_radius"] else "SAFE"), dist

# ============================
# ROUTES
# ============================
@app.get("/")
def root():
    return RedirectResponse("/login")

# LOGIN
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
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
        request.session["pending_2fa"] = True
        request.session["patient_id"] = patient_id
        request.session["username"] = username
        request.session["role"] = user["role"]

        import random
        otp = str(random.randint(1000, 9999))
        request.session["otp_code"] = otp

        log_event(
            event_type="LOGIN_SUCCESS",
            username=username,
            role=user["role"],
            details=f"User ID {patient_id} logged in and moved to OTP"
        )

        print("OTP:", otp)
        return RedirectResponse("/verify-otp", status_code=302)

    log_event(
        event_type="LOGIN_FAILED",
        username=username,
        role="unknown",
        details=f"Failed login attempt for ID {patient_id}"
    )

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid Patient ID or credentials"}
    )


@app.get("/verify-otp", response_class=HTMLResponse)
def verify_otp_page(request: Request):
    if not request.session.get("pending_2fa"):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "verify_otp.html",
        {
            "request": request,
            "error": None
        }
    )

# OTP
@app.post("/verify-otp", response_class=HTMLResponse)
def verify_otp_post(request: Request, otp: str = Form(...)):
    if not request.session.get("pending_2fa"):
        return RedirectResponse("/login", status_code=302)

    real_otp = request.session.get("otp_code")

    if otp == real_otp:
        request.session["logged_in"] = True
        request.session["pending_2fa"] = False
        request.session.pop("otp_code", None)
        return RedirectResponse("/dashboard", status_code=302)

    return templates.TemplateResponse(
        "verify_otp.html",
        {
            "request": request,
            "error": "Invalid OTP code"
        }
    )

# LOGOUT
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# DASHBOARD 
@app.get("/dashboard")
def dashboard(request: Request):

    if not require_login(request):
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "patient": PATIENT
        }
    )

# OVERVIEW
@app.get("/overview")
def overview(request: Request):
    if not require_login(request):
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "patient": PATIENT
        }
    )

# MEDICAL
@app.get("/medical-profile")
def medical_profile(request: Request):
    return templates.TemplateResponse("medical_profile.html", {
        "request": request,
        "role": request.session.get("role"),
        "patient": PATIENT
    })
@app.post("/update-medical-profile")
async def update_medical_profile(
    request: Request,
    diagnosis: str = Form(...),
    diseases: str = Form(...),
    allergies: str = Form(...),
    weight: str = Form(...)
):
    if request.session.get("role") != "doctor":
        raise HTTPException(status_code=403)

    PATIENT["diagnosis"] = diagnosis
    PATIENT["diseases"] = diseases
    PATIENT["allergies"] = allergies
    PATIENT["weight"] = weight

    return RedirectResponse("/medical-profile?updated=1", status_code=303)

# LIVE MONITOR
@app.get("/live-monitoring")
def live(request: Request):

    if not require_login(request):
        return RedirectResponse("/login", status_code=302)

    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT lat, lon, status, distance_km
    FROM telemetry
    ORDER BY id DESC
    LIMIT 1
    """)

    row = cur.fetchone()
    conn.close()

    SAFE_LAT = 24.7136
    SAFE_LON = 46.6753

    if row:
        lat = row[0]
        lon = row[1]
        status = row[2]

        distance = ((lat - SAFE_LAT) ** 2 + (lon - SAFE_LON) ** 2) ** 0.5 * 111

        latest_data = {
            "lat": lat,
            "lon": lon,
            "status": status,
            "distance": round(distance, 2)
        }
    else:
        latest_data = None

    return templates.TemplateResponse(
        "live_monitoring.html",
        {
            "request": request,
            "patient": PATIENT,
            "data": latest_data
        }
    )

# LOCATION CONTROL
@app.get("/location-control")
def location(request: Request):

    if not require_role(request, ["admin"]):
        return RedirectResponse("/dashboard", status_code=302)

    print("SAFE_ZONE:", {
        "lat": settings["safe_lat"],
        "lng": settings["safe_lon"],
        "radius": settings["safe_radius"]
    })

    return templates.TemplateResponse(
        "location_control.html",
        {
            "request": request,
            "patient": PATIENT,
            "safe_zone": {
                "lat": settings["safe_lat"],
                "lng": settings["safe_lon"],
                "radius": settings["safe_radius"]
            }
        }
    )
 # TELEMETRY 
@app.get("/live-monitoring")
def live_monitoring(request: Request):
    if not require_login(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "live_monitoring.html",
        {
            "request": request,
            "patient": PATIENT
        }
    )

@app.get("/api/latest-telemetry")
def latest_telemetry():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT lat, lon, status, distance_km
    FROM telemetry
    ORDER BY id DESC
    LIMIT 1
    """)

    row = cur.fetchone()
    conn.close()

    if not row:
        return {"ok": False}

    return {
        "ok": True,
        "lat": row[0],
        "lon": row[1],
        "status": row[2],
        "distance": row[3]
    }
@app.post("/telemetry")
async def receive_telemetry(data: dict):

  
    device_id = data.get("device_id", "chip1")
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))

   
    safe_lat = float(settings.get("safe_lat", 24.7136))
    safe_lon = float(settings.get("safe_lon", 46.6753))
    safe_radius = float(settings.get("safe_radius", 0.2))

    
    distance_km = ((lat - safe_lat) ** 2 + (lon - safe_lon) ** 2) ** 0.5 * 111

    
    if distance_km <= safe_radius:
        status = "SAFE"
        app.state.last_alert_sent = False
    else:
        status = "ALERT"

        if not app.state.last_alert_sent:
            try:
                send_whatsapp("🚨ALERT: Patient is OUTSIDE Safe Zone!")
            except Exception as e:
                print("WhatsApp Error:", e)

            app.state.last_alert_sent = True

    
    created_at = datetime.now(timezone.utc).isoformat()

   
    conn = sqlite3.connect("amancare.db")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO telemetry (device_id, lat, lon, status, distance_km, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        device_id,
        lat,
        lon,
        status,
        distance_km,
        created_at
    ))

    conn.commit()
    conn.close()

    
    return {
        "ok": True,
        "status": status,
        "distance_km": distance_km
    }
# ============================
# UPDATE LOCATION 
# ============================
@app.post("/update-safe-zone")
async def update_safe_zone(request: Request):
    data = await request.json()

    lat = float(data["lat"])
    lng = float(data["lng"])
    radius_km = float(data["radius_km"])

    settings["patient_lat"] = lat
    settings["patient_lon"] = lng
    settings["safe_lat"] = lat
    settings["safe_lon"] = lng
    settings["safe_radius"] = radius_km

    log_event(
        event_type="SAFE_ZONE_UPDATED",
        username=request.session.get("username", ""),
        role=request.session.get("role", ""),
        details=f"Safe zone updated to lat={lat}, lon={lng}, radius={radius_km}"
    )

    return JSONResponse({
        "success": True,
        "safe_zone": {
            "lat": settings["safe_lat"],
            "lng": settings["safe_lon"],
            "radius_km": settings["safe_radius"]
        }
    })

@app.get("/api/safe-zone")
def get_safe_zone():
    return {
        "lat": settings["safe_lat"],
        "lon": settings["safe_lon"],
        "radius": settings["safe_radius"]
    }