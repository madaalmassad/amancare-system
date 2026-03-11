document.addEventListener("DOMContentLoaded", function () {
    const mapEl = document.getElementById("map");
    if (!mapEl || typeof L === "undefined") return;

    const safeCenter = [24.7136, 46.6753];
    const safeZoneRadius = 120;

    const route = [
        [24.7136, 46.6753],
        [24.7139, 46.6758],
        [24.7142, 46.6762],
        [24.7140, 46.6768],
        [24.7134, 46.6771],
        [24.7129, 46.6767],
        [24.7126, 46.6760],
        [24.7128, 46.6754],
        [24.7133, 46.6750],
        [24.7138, 46.6752],
        [24.7146, 46.6779],
        [24.7150, 46.6783]
    ];

    const map = L.map("map").setView(safeCenter, 16);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);

    L.circle(safeCenter, {
        radius: safeZoneRadius,
        color: "#16a34a",
        weight: 2,
        fillColor: "#22c55e",
        fillOpacity: 0.12
    }).addTo(map);

    const patientIcon = L.divIcon({
        className: "patient-marker-wrap",
        html: `<div class="patient-live-dot"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    });

    let routeIndex = 0;
    const patientMarker = L.marker(route[0], { icon: patientIcon }).addTo(map);

    const travelledPath = L.polyline([route[0]], {
        color: "#155eef",
        weight: 4,
        opacity: 0.72
    }).addTo(map);

    function calcDistance(from, to) {
        return map.distance(L.latLng(from[0], from[1]), L.latLng(to[0], to[1]));
    }

    function updateDashboardStatus(position) {
        const distance = calcDistance(position, safeCenter);
        const insideSafeZone = distance <= safeZoneRadius;
        const statusText = insideSafeZone ? "SAFE" : "ALERT";

        const mainStatus = document.getElementById("mainStatusText");
        const mainStatusBox = document.getElementById("mainStatusBox");
        const monitorStatus = document.getElementById("monitorStatusText");
        const statusPill = document.getElementById("statusPill");
        const distanceText = document.getElementById("distanceText");
        const alertLevelText = document.getElementById("alertLevelText");

        if (mainStatus) {
            mainStatus.textContent = statusText;
            mainStatus.className = insideSafeZone ? "status-safe" : "status-alert";
        }

        if (mainStatusBox) {
            mainStatusBox.classList.remove("safe-box", "alert-box");
            mainStatusBox.classList.add(insideSafeZone ? "safe-box" : "alert-box");
        }

        if (monitorStatus) {
            monitorStatus.textContent = statusText;
            monitorStatus.className = insideSafeZone ? "status-safe" : "status-alert";
        }

        if (statusPill) {
            statusPill.textContent = statusText;
            statusPill.classList.remove("safe", "alert");
            statusPill.classList.add(insideSafeZone ? "safe" : "alert");
        }

        if (distanceText) {
            distanceText.textContent = `${Math.round(distance)} m`;
        }

        if (alertLevelText) {
            alertLevelText.textContent = insideSafeZone ? "Low" : "High";
        }

        patientMarker.bindPopup(`
      <div style="min-width:200px; font-family:Inter, sans-serif;">
        <strong>Mohammed Alajmi</strong><br>
        Status: <b style="color:${insideSafeZone ? "#16a34a" : "#dc2626"}">${statusText}</b><br>
        Location: Riyadh, Saudi Arabia<br>
        Distance: ${Math.round(distance)} m<br>
        Zone: ${insideSafeZone ? "Inside Safe Zone" : "Outside Safe Zone"}
      </div>
    `);
    }

    function animateMove(from, to, duration = 2200) {
        const start = performance.now();

        function frame(now) {
            const progress = Math.min((now - start) / duration, 1);
            const lat = from[0] + (to[0] - from[0]) * progress;
            const lng = from[1] + (to[1] - from[1]) * progress;
            const nextPos = [lat, lng];

            patientMarker.setLatLng(nextPos);
            travelledPath.addLatLng(nextPos);
            updateDashboardStatus(nextPos);

            if (progress < 1) requestAnimationFrame(frame);
        }

        requestAnimationFrame(frame);
    }

    updateDashboardStatus(route[0]);

    setInterval(() => {
        const nextIndex = (routeIndex + 1) % route.length;
        animateMove(route[routeIndex], route[nextIndex], 2200);
        routeIndex = nextIndex;
    }, 2600);

    setTimeout(() => {
        map.invalidateSize();
    }, 300);
});