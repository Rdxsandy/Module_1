"""
seed.py - Populate the Neon (PostgreSQL) database with representative demo data.

Run from the backend/ directory:
    python -m app.seed.demo_seed

Creates:
  - 2 demo users (ADMIN: admin/Admin@123, OPERATOR: operator/Operator@123)
  - 12 cameras across Delhi (Traffic, Police, Municipal departments)
  - 1 active watchlist entry for DL01AB1234 (high-priority stolen vehicle)
  - 12 vehicle events via MockEventSource (triggers alerts automatically)

Safe to run multiple times - skips if data already present.
"""
import asyncio
import sys
import os

# Allow running from backend/ dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, func
from app.database import SessionLocal, engine, Base
import app.models  # noqa: ensure all models registered

from app.models.camera import Camera
from app.models.watchlist import Watchlist
from app.models.user import User
from app.models.vehicle_event import VehicleEvent
from app.schemas.event import EventCreate
from app.services.event_service import process_event
from app.event_sources.mock_source import MockEventSource
from app.auth.security import hash_password

# ---------------------------------------------------------------------------
# Demo users  (password for both: 12345678)
# ---------------------------------------------------------------------------

USERS = [
    {"username": "admin",    "password": "Admin@123", "role": "ADMIN"},
    {"username": "operator", "password": "Operator@123", "role": "OPERATOR"},
]

# ---------------------------------------------------------------------------
# 12 cameras in Delhi
# ---------------------------------------------------------------------------

CAMERAS = [
    {"name": "Camera-01", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6139, "longitude": 77.2090, "status": "ONLINE"},
    {"name": "Camera-02", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6155, "longitude": 77.2100, "status": "ONLINE"},
    {"name": "Camera-03", "department": "Traffic",   "camera_type": "Fixed", "owner": "Delhi Traffic Police", "latitude": 28.6170, "longitude": 77.2110, "status": "ONLINE"},
    {"name": "Camera-04", "department": "Police",    "camera_type": "PTZ",   "owner": "Delhi Police",         "latitude": 28.6180, "longitude": 77.2120, "status": "ONLINE"},
    {"name": "Camera-05", "department": "Police",    "camera_type": "ANPR",  "owner": "Delhi Police",         "latitude": 28.6185, "longitude": 77.2130, "status": "ONLINE"},
    {"name": "Camera-06", "department": "Municipal", "camera_type": "Fixed", "owner": "NDMC",                 "latitude": 28.6190, "longitude": 77.2140, "status": "MAINTENANCE"},
    {"name": "Camera-07", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6200, "longitude": 77.2150, "status": "ONLINE"},
    {"name": "Camera-08", "department": "Police",    "camera_type": "PTZ",   "owner": "Delhi Police",         "latitude": 28.6210, "longitude": 77.2160, "status": "ONLINE"},
    {"name": "Camera-09", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6220, "longitude": 77.2170, "status": "ONLINE"},
    {"name": "Camera-10", "department": "Municipal", "camera_type": "Fixed", "owner": "NDMC",                 "latitude": 28.6230, "longitude": 77.2180, "status": "OFFLINE"},
    {"name": "Camera-11", "department": "Police",    "camera_type": "ANPR",  "owner": "Delhi Police",         "latitude": 28.6240, "longitude": 77.2190, "status": "ONLINE"},
    {"name": "Camera-12", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6250, "longitude": 77.2200, "status": "ONLINE"},
]

WATCHLIST = [
    {
        "identifier": "DL01AB1234",
        "entity_type": "VEHICLE",
        "description": "High-priority wanted/stolen vehicle - demo target",
        "priority": "HIGH",
        "active": True,
    }
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # --- Users ---
        existing_users = (await db.execute(select(func.count(User.id)))).scalar_one()
        if existing_users == 0:
            for u in USERS:
                db.add(User(
                    username=u["username"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True,
                ))
            await db.commit()
            print(f"  [OK] Seeded {len(USERS)} users")
            for u in USERS:
                print(f"       {u['role']:9s} -> {u['username']} / {u['password']}")
        else:
            print(f"  [--] Users already present ({existing_users}), skipping")

        # --- Cameras ---
        existing_cameras = (await db.execute(select(func.count(Camera.id)))).scalar_one()
        if existing_cameras == 0:
            for cam_data in CAMERAS:
                db.add(Camera(**cam_data))
            await db.commit()
            print(f"  [OK] Seeded {len(CAMERAS)} cameras")
        else:
            print(f"  [--] Cameras already present ({existing_cameras}), skipping")

        # --- Watchlist ---
        existing_wl = (await db.execute(select(func.count(Watchlist.id)))).scalar_one()
        if existing_wl == 0:
            for wl_data in WATCHLIST:
                db.add(Watchlist(**wl_data))
            await db.commit()
            print(f"  [OK] Seeded {len(WATCHLIST)} watchlist entries")
        else:
            print(f"  [--] Watchlist already present ({existing_wl}), skipping")

        # --- Events via MockEventSource ---
        existing_events = (await db.execute(select(func.count(VehicleEvent.id)))).scalar_one()
        if existing_events == 0:
            # MockEventSource's callback is plain-sync (shared interface with real
            # adapters); collect payloads first, then await process_event for each.
            collected: list[EventCreate] = []
            source = MockEventSource(on_event=collected.append, delay=0.0)
            source.start()

            for payload in collected:
                event, alert = await process_event(db, payload)
                alert_info = f" -> ALERT #{alert.id}" if alert else ""
                print(f"    Event #{event.id}: {event.vehicle_number} @ Camera-{event.camera_id:02d}{alert_info}")
            print("  [OK] Seeded 12 vehicle events (MockEventSource)")
        else:
            print(f"  [--] Events already present ({existing_events}), skipping")


if __name__ == "__main__":
    print("Seeding CCTV GIS PoC database...")
    asyncio.run(seed())
    print("Done. Run: uvicorn app.main:app --reload")
