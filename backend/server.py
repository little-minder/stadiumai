"""
StadiumAI backend.

Built on the Python standard library only (http.server) so the whole
project runs anywhere with just `python3 server.py` - no pip install,
no API keys, no internet required. Every place you'd plug in a real
service (LLM, CCTV/YOLO, Google Maps, MongoDB) is called out in comments.

For a production build, swap this file for FastAPI + Uvicorn + WebSockets
(see requirements.txt) - the route shapes below map 1:1 onto FastAPI path
operations, so the migration is mechanical.
"""
import json
import queue
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import data
import rag
import simulator
import auth

PORT = 8000

# in-memory order log (would be MongoDB/Firebase in production)
ORDERS = []
PARKING_RESERVATIONS = []


def _cors(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # quiet

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        _cors(self)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _current_username(self):
        auth_header = self.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        return auth.username_for_token(token) if token else "Guest"

    def do_OPTIONS(self):
        self.send_response(204)
        _cors(self)
        self.end_headers()

    # ---------------------------------------------------------- GET
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/events":
            return self._sse_stream()

        routes = {
            "/api/schedule": lambda: self._json(data.SCHEDULE),
            "/api/gates": lambda: self._json(data.GATES),
            "/api/food-stalls": lambda: self._json(self._food_with_live_wait()),
            "/api/parking": lambda: self._json(self._parking_view()),
            "/api/dashboard": lambda: self._json(self._dashboard()),
            "/api/orders": lambda: self._json(ORDERS),
            "/api/auth/users": lambda: self._json(auth.recent_logins()),
        }

        if path == "/api/facilities":
            ftype = qs.get("type", [None])[0]
            near = qs.get("near", [None])[0]
            return self._json(self._facilities(ftype, near))

        if path in routes:
            return routes[path]()

        if path == "/" or path == "/health":
            return self._json({"status": "ok", "service": "StadiumAI backend"})

        self._json({"error": "not found", "path": path}, status=404)

    # ---------------------------------------------------------- POST
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        payload = self._read_json()

        if path == "/api/chat":
            question = payload.get("message", "")
            lang = payload.get("lang", "en")
            return self._json(rag.answer(question, lang))

        if path == "/api/auth/login":
            record = auth.login(payload.get("username"), payload.get("email"))
            if not record:
                return self._json({"error": "username is required"}, status=400)
            return self._json(record, status=201)

        if path == "/api/food-order":
            result = self._place_food_order(payload)
            status = 400 if "error" in result else 201
            return self._json(result, status=status)

        if path == "/api/parking/reserve":
            zone_id = payload.get("zone_id")
            slot = simulator.STATE["parking"].get(zone_id)
            if not slot:
                return self._json({"error": "unknown zone"}, status=404)
            reservation = {
                "reservation_id": f"PARK-{len(PARKING_RESERVATIONS) + 1:04d}",
                "zone_id": zone_id,
            }
            PARKING_RESERVATIONS.append(reservation)
            slot["occupied"] = min(slot["capacity"], slot["occupied"] + 1)
            return self._json(reservation, status=201)

        if path == "/api/emergency":
            kind = payload.get("kind", "Reported emergency")
            zone = payload.get("zone", random.choice(data.ZONES))
            incident = simulator.report_emergency(kind, zone)
            return self._json(incident, status=201)

        if path == "/api/companion":
            # Personalized Fan Companion: best gate/stall/restroom/shop/exit
            # given the fan's current zone + preferences.
            zone = payload.get("zone", "A")
            prefs = payload.get("preferences", {})
            return self._json(self._companion(zone, prefs))

        self._json({"error": "not found", "path": path}, status=404)

    # ---------------------------------------------------------- helpers
    def _place_food_order(self, payload):
        stall_id = payload.get("stall_id")
        item_ids = payload.get("item_ids", [])
        payment_method = payload.get("payment_method", "cash")  # 'online' | 'cash'

        stall = next((s for s in data.FOOD_STALLS if s["id"] == stall_id), None)
        if not stall:
            return {"error": "unknown stall_id"}

        menu_by_id = {m["id"]: m for m in stall["menu"]}
        chosen = [menu_by_id[i] for i in item_ids if i in menu_by_id]
        if not chosen:
            return {"error": "no valid items selected"}

        total = sum(item["price"] for item in chosen)
        paid_online = payment_method == "online"

        order = {
            "order_id": f"ORD-{len(ORDERS) + 1:04d}",
            "username": self._current_username(),
            "stall_id": stall_id,
            "stall_name": stall["name"],
            "zone": stall["zone"],
            "items": chosen,
            "total_rupees": total,
            "payment_method": payment_method,
            "paid_online": paid_online,
            "payment_status": "Paid online" if paid_online else "Pay at counter (cash/card)",
            "status": "confirmed",
        }
        ORDERS.append(order)
        return order

    def _food_with_live_wait(self):
        out = []
        for stall in data.FOOD_STALLS:
            density = simulator.STATE["crowd"].get(stall["zone"], 40)
            wait = round(stall["base_wait"] * (0.5 + density / 70))
            out.append({**stall, "crowd_density": density, "estimated_wait_min": wait})
        out.sort(key=lambda s: s["estimated_wait_min"])
        return out

    def _parking_view(self):
        out = []
        for p in data.PARKING_ZONES:
            live = simulator.STATE["parking"][p["id"]]
            free = live["capacity"] - live["occupied"]
            out.append({**p, "occupied": live["occupied"], "free": free,
                        "occupancy_pct": round(100 * live["occupied"] / live["capacity"])})
        return out

    def _facilities(self, ftype, near_zone):
        items = data.FACILITIES
        if ftype:
            items = [f for f in items if f["type"] == ftype]
        if near_zone:
            items = sorted(items, key=lambda f: abs(ord(f["zone"]) - ord(near_zone.upper())))
        return items

    def _companion(self, zone, prefs):
        zone = zone.upper()
        nearest = lambda ftype: simulator._nearest_facility(zone, ftype) if hasattr(simulator, "_nearest_facility") else None
        stalls = self._food_with_live_wait()
        best_stall = min(stalls, key=lambda s: s["estimated_wait_min"])
        return {
            "zone": zone,
            "suggested_gate": f"GATE-{zone}",
            "suggested_food_stall": best_stall,
            "suggested_restroom": simulator._nearest_facility(zone, "restroom"),
            "suggested_shop": simulator._nearest_facility(zone, "shop"),
            "suggested_exit": simulator._nearest_facility(zone, "exit"),
            "crowd_density_here": simulator.STATE["crowd"].get(zone, 0),
        }

    def _dashboard(self):
        snap = simulator.snapshot()
        avg_density = round(sum(snap["crowd"].values()) / len(snap["crowd"]), 1)
        busiest_zone = max(snap["crowd"], key=snap["crowd"].get)
        deployed = [s for s in snap["staff"] if s["status"] != "available"]
        return {
            "avg_density": avg_density,
            "busiest_zone": busiest_zone,
            "crowd": snap["crowd"],
            "active_incidents": [i for i in snap["incidents"] if i["status"] in ("predicted", "active")][:10],
            "staff": snap["staff"],
            "staff_deployed_count": len(deployed),
            "parking": self._parking_view(),
            "carbon": snap["carbon"],
            "orders_count": len(ORDERS),
            "recent_logins": auth.recent_logins(8),
        }

    def _sse_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        _cors(self)
        self.end_headers()

        q = simulator.subscribe()
        try:
            # send an initial full snapshot so the UI has data immediately
            init = simulator.snapshot()
            self.wfile.write(f"event: snapshot\ndata: {json.dumps(init)}\n\n".encode())
            self.wfile.flush()

            while True:
                try:
                    event = q.get(timeout=15)
                    msg = f"event: {event['type']}\ndata: {json.dumps(event['payload'])}\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            simulator.unsubscribe(q)


def main():
    simulator.start_background_thread()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"StadiumAI backend running on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
