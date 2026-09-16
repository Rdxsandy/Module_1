import asyncio
import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _process_simulated_event(payload: EventCreate):
    """Each event gets its own short-lived session — safe across the
    background simulator thread without holding a session open for the
    whole run."""
    async with SessionLocal() as db:
        try:
            await process_event(db, payload)
        except Exception as e:
            print(f"Simulator error processing event: {e}")


def _on_simulated_event(payload: EventCreate):
    """Sync callback required by the EventSource interface (it runs on a
    plain background thread, not the asyncio event loop) — bridges into
    the async DB session with its own event loop."""
    asyncio.run(_process_simulated_event(payload))


def _run(source: LiveTrafficSimulator):
    global is_running
    try:
        source.start()
    finally:
        is_running = False


@router.post("/start")
async def start_simulator(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    global _simulator_source, is_running
    if is_running:
        raise HTTPException(status_code=400, detail="Simulator is already running")

    online_result = await db.execute(select(Camera).filter(Camera.status == "ONLINE"))
    online_cameras = online_result.scalars().all()
    if online_cameras:
        camera_rows = online_cameras
    else:
        all_result = await db.execute(select(Camera))
        camera_rows = all_result.scalars().all()

    cameras = [{"name": c.name, "latitude": c.latitude, "longitude": c.longitude} for c in camera_rows]
    if not cameras:
        raise HTTPException(status_code=400, detail="No cameras registered — cannot start simulator")

    wl_result = await db.execute(select(Watchlist).filter(Watchlist.active.is_(True)))
    watchlist_plates = [w.identifier for w in wl_result.scalars().all()]

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
async def emit_single_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Manually emit a single event (like start but 1 event without thread)"""
    try:
        event, alert = await process_event(db, payload)
        return {"status": "emitted", "event_id": event.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
def get_simulator_status(
    _: User = Depends(get_current_user),
):
    global is_running
    return {"running": is_running}
