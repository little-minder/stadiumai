# StadiumAI — Smart Stadium & Tournament Operations Assistant

A working, runnable prototype (frontend + backend) of the concept: real-time
crowd intelligence, an AI fan assistant, emergency response, smart food/parking,
a digital twin view, and an organizer dashboard — all driven by a live
event stream.

The whole thing runs **with zero installs and zero API keys**: the backend
uses only the Python standard library, and the frontend is a single static
HTML file. That's a deliberate choice so it's guaranteed to run in any judge's
environment in under a minute — every place a real production service
(LLM, CCTV/YOLO, Google Maps, MongoDB) would plug in is called out in code
comments, with a `requirements.txt` documenting exactly what to add.

## Run it (2 terminals, ~30 seconds)

**Terminal 1 — backend**
```bash
cd backend
python3 server.py
# StadiumAI backend running on http://0.0.0.0:8000
```

**Terminal 2 — frontend**
```bash
cd frontend
python3 -m http.server 5500
```
Open **http://localhost:5500** in your browser.

That's it — the dashboard connects to the backend over a live Server-Sent
Events stream (`/events`) and starts updating immediately: crowd density per
zone, incident predictions, parking availability, staff dispatch, and carbon
metrics all drift in real time from a background simulation thread, the way
live CCTV/IoT sensors would feed a real deployment.

> If you open `frontend/index.html` directly by double-clicking it, that
> also works in most browsers — the http.server step is just the safest
> default for CORS/EventSource behavior.

## What's real vs. simulated in this build

| Feature | This demo | Production swap-in |
|---|---|---|
| Sign-in / authentication | Real session flow: username + email recorded with a login timestamp, session token stored in `localStorage`, gates the whole app | Real credential store (hashed passwords) + provider like Auth0/Firebase Auth/Cognito, same response shape |
| Fan Assistant | Real retrieval (keyword/overlap scoring over a stadium knowledge base) + templated answer, offline | Swap `rag.py`'s `_compose()` for an LLM call (OpenAI/Azure OpenAI + a real vector DB like FAISS/ChromaDB) — retrieval logic stays the same |
| Crowd density | Simulated per-zone sine-wave + noise, updated every 2s | YOLO/OpenCV person-count from CCTV, or WiFi/BLE occupancy sensors, aggregated per zone |
| Incident Predictor | Rule-based: flags a zone 15–30 min before it would hit critical density | Anomaly-detection model on the same CCTV pipeline (density spike, flow-reversal, fall detection) |
| Staff/volunteer dispatch | Nearest-available-by-zone assignment | Same logic, backed by a real staff roster + push notifications |
| Digital Twin | 2D live canvas (zones + moving crowd dots) | Full 3D twin (Unity/Unreal or a WebGL engine) fed by the same live event stream |
| Multi-language | Small keyword-bridge dictionary (ES/FR/PT/AR → EN) so retrieval still matches | Real MT (Azure Translator / GPT) ahead of retrieval |
| Food payment | Order total computed server-side from a real priced menu (₹); "online" instantly marks the order paid, "cash" marks pay-at-counter | Real payment gateway (Razorpay/Stripe) webhook flips `paid_online` once payment actually clears |
| Maps/routing | Zone-letter-distance heuristic | Google Maps Directions/Distance Matrix API |
| Data store | In-memory (resets on restart) | MongoDB or Firebase, as in the original tech stack |

## Sign-in & theme

- On first load you'll see a **Sign In** screen. Enter any username, email and
  password (this demo doesn't verify passwords — it exists to *identify who's
  using the app*, per the brief). Submitting calls `POST /api/auth/login`,
  which records `{username, email, login_time}` server-side and returns a
  session token.
- The session is kept in the browser's `localStorage`, so refreshing keeps you
  signed in; **Sign out** in the header clears it and returns you to the
  sign-in screen.
- The Organizer Dashboard's **Signed-in Users** card shows everyone who has
  logged in and when, straight from that same log.
- The 🌙 / 🌞 toggle in the header switches the whole UI between dark and
  light themes instantly, and remembers your choice for next time.

## Food ordering & payment

- The Food Ordering tab lists every stall's menu **grouped by zone**, with
  prices in ₹.
- Tap **Add** on any items to build a cart, choose **Pay online** or
  **Pay at counter**, then **Place Order**.
- The backend prices the order itself (never trusts a client-sent total),
  returns an `order_id`, and marks the order `paid_online: true/false` — the
  confirmation card on-screen shows exactly what you ordered, the total, the
  order ID, and whether it's already paid or due at the counter.



`requirements.txt` in `backend/` lists the exact packages for that upgrade
path (FastAPI, Uvicorn, websockets, OpenAI SDK, FAISS, OpenCV, Ultralytics
YOLO, Google Maps SDK) — the route shapes in `server.py` map 1:1 onto FastAPI
path operations, so migrating is mechanical, not a rewrite.

## Feature → file map

| Feature | Backend | Frontend tab |
|---|---|---|
| AI Fan Assistant | `rag.py`, `POST /api/chat` | Fan Assistant |
| Crowd Prediction | `simulator.py` (`_tick`), `GET /events` | Live Crowd Map |
| Digital Twin Stadium | `GET /events` (crowd stream) | Digital Twin |
| AI Incident Predictor | `simulator.py` (`_predict_and_raise_incident`) | Emergency, Organizer Dashboard |
| Emergency AI | `POST /api/emergency` | Emergency |
| Volunteer & Staff Copilot | `simulator.py` (`_assign_staff`) | Organizer Dashboard |
| Smart Food Ordering | `GET /api/food-stalls`, `POST /api/food-order` | Food Ordering |
| Smart Facility Finder | `GET /api/facilities` | Facility Finder |
| Personalized Fan Companion | `POST /api/companion` | Facility Finder (bottom card) |
| Smart Parking | `GET /api/parking`, `POST /api/parking/reserve` | Smart Parking |
| Carbon Footprint Dashboard | `simulator.py` (`STATE["carbon"]`) | Organizer Dashboard |
| Organizer Dashboard | `GET /api/dashboard` | Organizer Dashboard |

## API reference

```
GET  /health
GET  /events                    SSE stream: snapshot, crowd_update,
                                 incident_alert, staff_assignment,
                                 parking_update, carbon_update
GET  /api/schedule
GET  /api/gates
GET  /api/facilities?type=&near=
GET  /api/food-stalls           each stall's menu includes id/name/price (₹)
GET  /api/parking
GET  /api/dashboard             includes recent_logins for the organizer view
POST /api/auth/login      { username, email } → { token, username, email, login_time }
POST /api/chat             { message, lang }
POST /api/food-order       { stall_id, item_ids[], payment_method: "online"|"cash" }
                            → { order_id, items[], total_rupees, paid_online, payment_status }
POST /api/parking/reserve  { zone_id }
POST /api/emergency        { kind, zone }
POST /api/companion        { zone, preferences }
```

Send `Authorization: Bearer <token>` (the token returned from `/api/auth/login`)
on `/api/food-order` and `/api/emergency` so the order/incident is attributed
to the signed-in user — the frontend does this automatically.

## Architecture

```
Browser (frontend/index.html)
   │  fetch() + EventSource (SSE)
   ▼
FastAPI-shaped stdlib HTTP server (backend/server.py)
   │
   ├── rag.py         → AI Fan Assistant (retrieval + generation)
   ├── simulator.py    → crowd/incident/parking/staff/carbon engine
   │                      (background thread, pub/sub to SSE clients)
   └── data.py         → stadium knowledge base, gates, facilities,
                          food stalls, parking zones, schedule
```
