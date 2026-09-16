from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import threading

from app.database import get_db, SessionLocal
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.camera import Camera
from app.models.watchlist import Watchlist
from app.event_sources.traffic_simulator import LiveTrafficSimulator
from app.services.event_service import process_event
from app.schemas.event import EventCreate

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# Global state for the live multi-vehicle traffic simulator
_simulator_source: LiveTrafficSimulator | None = None
is_running = False


def _on_simulated_event(payload: EventCreate):
    """Each event gets its own short-lived session — safe across the
    background simulator thread without holding a session open for the
    whole run."""
    db = SessionLocal()
    try:
        process_event(db, payload)
    except Exception as e:
        print(f"Simulator error processing event: {e}")
    finally:
        db.close()


def _run(source: LiveTrafficSimulator):
    global is_running
    try:
        source.start()
    finally:
        is_running = False


@router.post("/start")
def start_simulator(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    global _simulator_source, is_running
    if is_running:
        raise HTTPException(status_code=400, detail="Simulator is already running")

    cameras = [
        {"name": c.name, "latitude": c.latitude, "longitude": c.longitude}
        for c in db.query(Camera).filter(Camera.status == "ONLINE").all()
    ] or [
        {"name": c.name, "latitude": c.latitude, "longitude": c.longitude}
        for c in db.query(Camera).all()
    ]
    if not cameras:
        raise HTTPException(status_code=400, detail="No cameras registered — cannot start simulator")

    watchlist_plates = [
        w.identifier for w in db.query(Watchlist).filter(Watchlist.active.is_(True)).all()
    ]

    _simulator_source = LiveTrafficSimulator(
        on_event=_on_simulated_event,
        cameras=cameras,
        watchlist_plates=watchlist_plates,
        interval=2.0,
    )
    is_running = True
    thread = threading.Thread(target=_run, args=(_simulator_source,), daemon=True)
    thread.start()
    return {
        "status": "started",
        "vehicle_count": len(_simulator_source.plates),
        "camera_count": len(cameras),
    }


@router.post("/stop")
def stop_simulator(
    user: User = Depends(require_admin),
):
    global is_running, _simulator_source
    is_running = False
    if _simulator_source:
        _simulator_source.stop()
    return {"status": "stopped"}


@router.post("/emit")
def emit_single_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Manually emit a single event (like start but 1 event without thread)"""
    try:
        event, alert = process_event(db, payload)
        return {"status": "emitted", "event_id": event.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
def get_simulator_status(
    _: User = Depends(get_current_user),
):
    global is_running
    return {"running": is_running}
