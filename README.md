# CCTV Centralised Intelligence Platform

A full-stack Proof-of-Concept demonstrating a central camera registry, real-time vehicle tracking, GIS mapping, and watchlist-based alerting — **without requiring any real CCTV hardware**. It features simulated AI Event Ingestion, Role-Based Access Control (RBAC), and Audit Logs.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python |
| Database | Neon PostgreSQL (via SQLAlchemy) |
| Frontend | React 18 + Vite |
| Map | react-leaflet + OpenStreetMap |
| Schemas | Pydantic v2 |

---

## Quick Start

### 1. Backend

```bash
docker compose up -d db

cd backend

# (Windows) create virtualenv
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Seed the database
python -m app.seed.demo_seed

# Start API server
uvicorn app.main:app --reload
```

API runs at **http://localhost:8000**
Swagger docs at **http://localhost:8000/docs**

---

### 2. Frontend

```bash
cd frontend

npm install
npm run dev
```

UI runs at **http://localhost:5173**

---

## Screens

| Screen | Route | Description |
|---|---|---|
| Dashboard | `/` | Stats cards, recent alerts, quick nav |
| Camera Registry | `/cameras` | List, search, filter, add cameras |
| GIS Map | `/map` | All cameras on map, vehicle route overlay |
| Vehicle Tracking | `/tracking` | Search plate → history + route + watchlist badge |
| Alerts | `/alerts` | All alerts, acknowledge, resolve, filter |
| Watchlist | `/watchlist` | Add, remove, and view watchlist items (ADMIN only for write) |

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Get JWT token (Demo: `admin`/`Admin@123` or `operator`/`Operator@123`) |
| GET | `/api/cameras` | List cameras (filters: dept, status, type, search) |
| POST | `/api/cameras` | Onboard a new camera (ADMIN only) |
| POST | `/api/cameras/bulk-upload` | Upload a CSV file of cameras (ADMIN only) |
| POST | `/api/events` | **Canonical ingestion** → watchlist match → alert |
| GET | `/api/events` | Search events (vehicle_number, camera_id, time range) |
| GET | `/api/vehicles/{plate}/history` | Ordered movement history with camera names |
| GET | `/api/alerts` | List alerts (filter by status, vehicle) |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge alert |
| POST | `/api/alerts/{id}/resolve` | Resolve alert |
| GET | `/api/watchlist` | List watchlist |
| POST | `/api/watchlist` | Add to watchlist (ADMIN only) |

---

## Demo Flow (Evaluator Script)

1. **Login** — Sign in as `admin` (password: `Admin@123`) or `operator` (password: `Operator@123`).
2. **Dashboard** — see 12 cameras, stats, recent alerts.
3. **Cameras** — full registry table, filter by department.
4. **Bulk Upload** — click "Bulk Upload", download template, select CSV and import it. See live errors for bad rows. This will generate an **Audit Log**.
5. **GIS Map** — 12+ markers on Delhi map with popup details.
6. **Watchlist** — View the watchlist. Admins can add new `VEHICLE` or `PERSON` entries with priority.
7. **Vehicle Tracking** — enter `DL01AB1234` → 12-stop history + route on map, watchlist badge.
8. **Send Event** — click "Send Demo Event" on tracking page → simulated AI triggers a live alert.
9. **Alerts** — alert appears with severity, vehicle, camera, reason. Click **Acknowledge**, then **Resolve**.

---

## Architecture & Extensibility

```
React (UI)
   │  REST/JSON
FastAPI (API + Business Logic + Audit Logs)
   │  SQLAlchemy
Neon PostgreSQL (via DATABASE_URL env var)

EventSource interface (event_sources/base.py)
   ├── MockEventSource  ← used now (Simulates Deterministic AI Events)
   └── FutureRTSPEventSource  ← real feeds slot in here
```

When real government CCTV feeds are provided, only `FutureRTSPEventSource` needs to be implemented. The watchlist, alert, history and GIS layers remain unchanged.

---

## Environment Variables

Copy `.env.example` to `.env`:

```
DATABASE_URL=postgresql://user:password@ep-example-12345.us-east-2.aws.neon.tech/dbname?sslmode=require
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

To switch to PostgreSQL:
```
DATABASE_URL=postgresql://user:pass@localhost/cctv
```
