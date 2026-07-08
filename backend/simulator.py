"""
Simulates the IoT / CCTV / sensor layer in real time.

Production swap-in points (kept simple & obvious on purpose):
  - crowd density  -> YOLO/OpenCV person-count from CCTV streams, or WiFi/BLE
                       occupancy sensors, aggregated per zone.
  - incidents      -> anomaly-detection model (e.g. sudden density spike,
                       flow-reversal, fall detection) running on the same
                       CCTV pipeline, plus manual staff reports.
  - parking        -> ANPR cameras / ultrasonic slot sensors per bay.

This module runs a background thread that mutates STATE and appends
events onto an in-memory pub/sub broadcaster that the SSE endpoint reads.
"""
import math
import random
import threading
import time
import queue
import itertools
from datetime import datetime, timedelta

from data import ZONES, PARKING_ZONES, FACILITIES

_start = time.time()
_lock = threading.Lock()

STATE = {
    "crowd": {z: 30 for z in ZONES},          # % density per zone
    "parking": {p["id"]: {"occupied": random.randint(20, 60), "capacity": p["capacity"]} for p in PARKING_ZONES},
    "incidents": [],                            # active predicted/real incidents
    "staff": [
        {"id": "S-01", "name": "Volunteer Ana", "role": "Volunteer", "zone": "A", "status": "available"},
        {"id": "S-02", "name": "Volunteer Leo", "role": "Volunteer", "zone": "C", "status": "available"},
        {"id": "S-03", "name": "Security Kim", "role": "Security", "zone": "E", "status": "available"},
        {"id": "S-04", "name": "Security Omar", "role": "Security", "zone": "G", "status": "available"},
        {"id": "S-05", "name": "Medic Sara", "role": "Medical", "zone": "D", "status": "available"},
        {"id": "S-06", "name": "Medic Tom", "role": "Medical", "zone": "G", "status": "available"},
    ],
    "carbon": {"energy_kwh": 12000, "waste_kg": 800, "transport_co2_kg": 4200},
}

_incident_id_counter = itertools.count(1)

# each connected SSE client gets its own Queue
_subscribers = []


def subscribe():
    q = queue.Queue()
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def _publish(event_type, payload):
    with _lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait({"type": event_type, "payload": payload})
        except queue.Full:
            pass


def _predict_and_raise_incident(zone, density):
    """AI Incident Predictor: flags a zone trending toward overload
    15-30 minutes before it would become critical, based on rate of change."""
    risk = min(99, int(density + random.uniform(5, 20)))
    eta_minutes = random.randint(15, 30)
    incident = {
        "id": f"INC-{next(_incident_id_counter):04d}",
        "kind": random.choice(["Gate overload risk", "Congestion build-up", "Possible bottleneck"]),
        "zone": zone,
        "risk_score": risk,
        "predicted": True,
        "eta_minutes": eta_minutes,
        "created_at": datetime.utcnow().isoformat(),
        "status": "predicted",
        "nearest_medical": _nearest_facility(zone, "medical"),
        "recommended_route": _alt_route(zone),
    }
    STATE["incidents"].insert(0, incident)
    STATE["incidents"] = STATE["incidents"][:20]
    _assign_staff(zone, incident["id"])
    _publish("incident_alert", incident)


def _nearest_facility(zone, ftype):
    candidates = [f for f in FACILITIES if f["type"] == ftype]
    if not candidates:
        return None
    # naive "nearest" by zone-letter distance
    def dist(f):
        return abs(ord(f["zone"]) - ord(zone))
    return min(candidates, key=dist)


def _alt_route(zone):
    idx = ZONES.index(zone)
    alt = ZONES[(idx + 3) % len(ZONES)]
    return f"Route via Gate {alt} concourse (lower congestion)"


def _assign_staff(zone, incident_id):
    with _lock:
        available = [s for s in STATE["staff"] if s["status"] == "available"]
        if not available:
            return
        # prefer nearest zone
        available.sort(key=lambda s: abs(ord(s["zone"]) - ord(zone)))
        staff = available[0]
        staff["status"] = f"dispatched -> {incident_id}"
    _publish("staff_assignment", {"staff": staff, "incident_id": incident_id, "zone": zone})


def _tick():
    t = (time.time() - _start) / 20.0
    for i, z in enumerate(ZONES):
        base = 45 + 35 * math.sin(t + i)
        noise = random.uniform(-8, 8)
        density = max(3, min(99, base + noise))
        prev = STATE["crowd"][z]
        STATE["crowd"][z] = round(density, 1)
        # Predict incident if density climbing fast and high
        if density > 78 and density > prev and random.random() < 0.12:
            _predict_and_raise_incident(z, density)

    _publish("crowd_update", STATE["crowd"])

    # parking drift
    for p in PARKING_ZONES:
        slot = STATE["parking"][p["id"]]
        delta = random.randint(-10, 12)
        slot["occupied"] = max(0, min(slot["capacity"], slot["occupied"] + delta))
    _publish("parking_update", STATE["parking"])

    # carbon dashboard drift
    c = STATE["carbon"]
    c["energy_kwh"] += random.randint(5, 40)
    c["waste_kg"] += random.randint(0, 5)
    c["transport_co2_kg"] += random.randint(2, 15)
    _publish("carbon_update", c)

    # staff recover over time
    with _lock:
        for s in STATE["staff"]:
            if s["status"] != "available" and random.random() < 0.05:
                s["status"] = "available"


def run_forever():
    while True:
        _tick()
        time.sleep(2)


def start_background_thread():
    th = threading.Thread(target=run_forever, daemon=True)
    th.start()
    return th


def snapshot():
    with _lock:
        return {
            "crowd": dict(STATE["crowd"]),
            "parking": {k: dict(v) for k, v in STATE["parking"].items()},
            "incidents": list(STATE["incidents"]),
            "staff": [dict(s) for s in STATE["staff"]],
            "carbon": dict(STATE["carbon"]),
        }


def report_emergency(kind, zone):
    """Fan/staff-triggered real emergency (Emergency AI)."""
    incident = {
        "id": f"INC-{next(_incident_id_counter):04d}",
        "kind": kind or "Reported emergency",
        "zone": zone,
        "risk_score": 95,
        "predicted": False,
        "eta_minutes": 0,
        "created_at": datetime.utcnow().isoformat(),
        "status": "active",
        "nearest_medical": _nearest_facility(zone, "medical"),
        "recommended_route": _alt_route(zone),
        "evacuation_exit": _nearest_facility(zone, "exit"),
    }
    STATE["incidents"].insert(0, incident)
    _assign_staff(zone, incident["id"])
    _publish("incident_alert", incident)
    return incident
