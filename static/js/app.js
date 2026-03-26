console.log("Advanced tracking app.js loaded");

let map = null;
let marker = null;
let circle = null;
let trailLine = null;

const baseLat = 24.7136;
const baseLng = 46.6753;
const safeRadiusMeters = 250;

const path = [
    [24.7136, 46.6753],
    [24.7145, 46.6765],
    [24.7155, 46.6780],
    [24.7170, 46.6795], // ALERT
    [24.7180, 46.6810],
    [24.7160, 46.6785],
    [24.7145, 46.6760],
    [24.7136, 46.6753]
];

let currentIndex = 0;
let visitedPoints = [[baseLat, baseLng]];

// ================= STATUS =================
function updateStatus(status, distanceMeters, lat, lng) {
    const mainStatusText = document.getElementById("mainStatusText");
    const liveStatus = document.getElementById("liveStatus");
    const liveDistance = document.getElementById("liveDistance");
    const zoneStatus = document.getElementById("zoneStatus");
    const movementStatus = document.getElementById("movementStatus");
    const liveLocation = document.getElementById("liveLocation");
    const liveUpdated = document.getElementById("liveUpdated");
    const topBadgeStatus = document.getElementById("topBadgeStatus");
    const mainStatusBox = document.getElementById("mainStatusBox");

    if (mainStatusText) {
        mainStatusText.textContent = status;
        mainStatusText.className = status === "SAFE" ? "status-safe" : "status-alert";
    }

    if (liveStatus) {
        liveStatus.textContent = status;
    }

    if (liveDistance) {
        const km = typeof distanceMeters === "number"
            ? (distanceMeters / 1000).toFixed(2)
            : "0.00";
        liveDistance.textContent = `${km} km`;
    }

    if (zoneStatus) {
        zoneStatus.textContent = status === "SAFE" ? "Inside Safe Zone" : "Outside Safe Zone";
    }

    if (movementStatus) {
        movementStatus.textContent = status === "SAFE" ? "Walking" : "Warning";
    }

    if (liveLocation && typeof lat === "number" && typeof lng === "number") {
        liveLocation.textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    }

    if (liveUpdated) {
        liveUpdated.textContent = new Date().toLocaleTimeString();
    }

    if (topBadgeStatus) {
        topBadgeStatus.textContent = status;
        topBadgeStatus.className = status === "SAFE"
            ? "status-pill safe"
            : "status-pill alert";
    }

    if (mainStatusBox) {
        mainStatusBox.classList.remove("safe-box", "alert-box");
        mainStatusBox.classList.add(status === "SAFE" ? "safe-box" : "alert-box");
    }
}
// ================= POPUP =================
function updatePopup(lat, lng, status, distanceMeters) {
    if (!marker) return;

    marker.bindPopup(`
        <div style="font-family: Inter, Tajawal, sans-serif; line-height:1.7; min-width:220px;">
            <strong style="font-size:15px;">Mohammed Alajmi</strong><br>
            Age: 85<br>
            Condition: Alzheimer's Disease<br>
            Status: <span style="color:${status === "SAFE" ? "#16a34a" : "#dc2626"}; font-weight:700;">${status}</span><br>
            Distance: ${Math.round(distanceMeters)} meters<br>
            Location: ${lat.toFixed(4)}, ${lng.toFixed(4)}
        </div>
    `);
}

// ================= MAP =================
function initMap() {
    const mapEl = document.getElementById("map");
    if (!mapEl) return;

    map = L.map("map", {
        zoomControl: false,
        attributionControl: false
    }).setView([baseLat, baseLng], 16);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

    circle = L.circle([baseLat, baseLng], {
        radius: safeRadiusMeters,
        color: "#16a34a",
        fillColor: "#22c55e",
        fillOpacity: 0.08,
        weight: 2
    }).addTo(map);

    trailLine = L.polyline(visitedPoints, {
        color: "#2563eb",
        weight: 5,
        opacity: 0.85
    }).addTo(map);

    marker = L.marker([baseLat, baseLng]).addTo(map);

    updatePopup(baseLat, baseLng, "SAFE", 0);

    setTimeout(() => map.invalidateSize(), 500);
}

// ================= SMOOTH MOVE =================
function smoothMoveMarker(marker, newLatLng, duration = 400) {
    const start = marker.getLatLng();
    const startTime = performance.now();

    function animate(time) {
        const progress = Math.min((time - startTime) / duration, 1);

        const lat = start.lat + (newLatLng[0] - start.lat) * progress;
        const lng = start.lng + (newLatLng[1] - start.lng) * progress;


        marker.setLatLng([lat, lng]);

        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }

    requestAnimationFrame(animate);
}

// ================= MOVE =================
function moveMarker() {
    if (!marker || !map) return;

    currentIndex++;
    if (currentIndex >= path.length) {
        currentIndex = 0;
        visitedPoints = [[baseLat, baseLng]];
    }

    const [newLat, newLng] = path[currentIndex];

    // 🔥 حساب المسافة
    const distanceMeters = map.distance(
        [baseLat, baseLng],
        [newLat, newLng]
    );

    // 🔥 تحديد الحالة
    const status =
        distanceMeters > safeRadiusMeters ? "ALERT" : "SAFE";

    // 🔥 حركة ناعمة
    smoothMoveMarker(marker, [newLat, newLng]);

    visitedPoints.push([newLat, newLng]);
    if (trailLine) {
        trailLine.setLatLngs(visitedPoints);
    }

    // 🔥 تحديث
    updateStatus(status, distanceMeters, newLat, newLng);
    updatePopup(newLat, newLng, status, distanceMeters);

    // 🔥 لون الدائرة
    circle.setStyle({
        color: status === "SAFE" ? "#16a34a" : "#dc2626",
        fillColor: status === "SAFE" ? "#22c55e" : "#ef4444",
        fillOpacity: status === "SAFE" ? 0.08 : 0.12
    });

    map.panTo([newLat, newLng], {
        animate: true,
        duration: 1
    });

    console.log("STATUS:", status);
    console.log("DIST:", distanceMeters);
}

// ================= START =================
document.addEventListener("DOMContentLoaded", function () {
    initMap();
    setInterval(moveMarker, 1200);
});