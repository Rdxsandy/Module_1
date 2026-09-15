"""
seed.py - Populate the SQLite database with representative demo data.

Run from the backend/ directory:
    python seed.py

Creates:
  - 2 demo users (ADMIN: admin/Admin@123, OPERATOR: operator/Operator@123)
  - 12 cameras across Delhi (Traffic, Police, Municipal departments)
  - 1 active watchlist entry for DL01AB1234 (high-priority stolen vehicle)
  - 12 vehicle events via MockEventSource (triggers alerts automatically)

Safe to run multiple times - skips if data already present.
"""
import sys
import os

# Allow running from backend/ dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
import app.models  # noqa: ensure all models registered

from app.models.camera import Camera
from app.models.watchlist import Watchlist
from app.models.user import User
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
    {"name": "Camera-01", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6139, "longitude": 77.2090, "status": "online"},
    {"name": "Camera-02", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6155, "longitude": 77.2100, "status": "online"},
    {"name": "Camera-03", "department": "Traffic",   "camera_type": "Fixed", "owner": "Delhi Traffic Police", "latitude": 28.6170, "longitude": 77.2110, "status": "online"},
    {"name": "Camera-04", "department": "Police",    "camera_type": "PTZ",   "owner": "Delhi Police",         "latitude": 28.6180, "longitude": 77.2120, "status": "online"},
    {"name": "Camera-05", "department": "Police",    "camera_type": "ANPR",  "owner": "Delhi Police",         "latitude": 28.6185, "longitude": 77.2130, "status": "online"},
    {"name": "Camera-06", "department": "Municipal", "camera_type": "Fixed", "owner": "NDMC",                 "latitude": 28.6190, "longitude": 77.2140, "status": "maintenance"},
    {"name": "Camera-07", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6200, "longitude": 77.2150, "status": "online"},
    {"name": "Camera-08", "department": "Police",    "camera_type": "PTZ",   "owner": "Delhi Police",         "latitude": 28.6210, "longitude": 77.2160, "status": "online"},
    {"name": "Camera-09", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6220, "longitude": 77.2170, "status": "online"},
    {"name": "Camera-10", "department": "Municipal", "camera_type": "Fixed", "owner": "NDMC",                 "latitude": 28.6230, "longitude": 77.2180, "status": "offline"},
    {"name": "Camera-11", "department": "Police",    "camera_type": "ANPR",  "owner": "Delhi Police",         "latitude": 28.6240, "longitude": 77.2190, "status": "online"},
    {"name": "Camera-12", "department": "Traffic",   "camera_type": "ANPR",  "owner": "Delhi Traffic Police", "latitude": 28.6250, "longitude": 77.2200, "status": "online"},
]

WATCHLIST = [
    {
        "vehicle_number": "DL01AB1234",
        "entity_type": "stolen_vehicle",
        "description": "High-priority wanted/stolen vehicle - demo target",
        "priority": "high",
        "active": True,
    }
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # --- Users ---
        existing_users = db.query(User).count()
        if existing_users == 0:
            for u in USERS:
                db.add(User(
                    username=u["username"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True,
                ))
            db.commit()
            print(f"  [OK] Seeded {len(USERS)} users")
            for u in USERS:
                print(f"       {u['role']:9s} -> {u['username']} / {u['password']}")
        else:
            print(f"  [--] Users already present ({existing_users}), skipping")

        # --- Cameras ---
        existing_cameras = db.query(Camera).count()
        if existing_cameras == 0:
            for cam_data in CAMERAS:
                db.add(Camera(**cam_data))
            db.commit()
            print(f"  [OK] Seeded {len(CAMERAS)} cameras")
        else:
            print(f"  [--] Cameras already present ({existing_cameras}), skipping")

        # --- Watchlist ---
        existing_wl = db.query(Watchlist).count()
        if existing_wl == 0:
            for wl_data in WATCHLIST:
                db.add(Watchlist(**wl_data))
            db.commit()
            print(f"  [OK] Seeded {len(WATCHLIST)} watchlist entries")
        else:
            print(f"  [--] Watchlist already present ({existing_wl}), skipping")

        # --- Events via MockEventSource ---
        from app.models.vehicle_event import VehicleEvent
        existing_events = db.query(VehicleEvent).count()
        if existing_events == 0:
            def on_event(payload):
                event, alert = process_event(db, payload)
                alert_info = f" -> ALERT #{alert.id}" if alert else ""
                print(f"    Event #{event.id}: {event.vehicle_number} @ Camera-{event.camera_id:02d}{alert_info}")

            source = MockEventSource(on_event=on_event, delay=0.0)
            source.start()
            print("  [OK] Seeded 12 vehicle events (MockEventSource)")
        else:
            print(f"  [--] Events already present ({existing_events}), skipping")

    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding CCTV GIS PoC database...")
    seed()
    print("Done. Run: uvicorn app.main:app --reload")
