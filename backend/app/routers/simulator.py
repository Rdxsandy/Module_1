import asyncio
import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, build_engine_and_sessionmaker
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
    _, sim_session_local = _get_worker_db()
    async with sim_session_local() as db:
        try:
            await process_event(db, payload)
        except Exception as e:
            print(f"Simulator error processing event: {e}")


# One dedicated event loop for the simulator thread, started lazily and
# reused for every event — NOT asyncio.run() per call, which creates and
# tears down a brand-new loop each time. That loop also gets its OWN
# engine/sessionmaker (never the app's main `engine`/`SessionLocal`):
# asyncpg connections are bound to the loop that opened them, so sharing one
# pool across two loops raises "Future attached to a different loop" /
# "Event loop is closed" on whichever request loses the race for a
# cross-loop connection. See the same fix in routers/camera_feed.py.
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_thread: threading.Thread | None = None
_worker_engine = None
_worker_session_local = None
_worker_loop_lock = threading.Lock()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop, _worker_loop_thread
    with _worker_loop_lock:
        if _worker_loop is None:
            _worker_loop = asyncio.new_event_loop()
            _worker_loop_thread = threading.Thread(
                target=_worker_loop.run_forever, daemon=True, name="simulator-worker-loop",
            )
            _worker_loop_thread.start()
        return _worker_loop


def _get_worker_db():
    """The simulator worker loop's own engine/sessionmaker — separate pool
    from app.database.engine, since that one belongs to the main FastAPI loop."""
    global _worker_engine, _worker_session_local
    with _worker_loop_lock:
        if _worker_engine is None:
            _worker_engine, _worker_session_local = build_engine_and_sessionmaker(
                pool_size=2, max_overflow=3
            )
        return _worker_engine, _worker_session_local


def _on_simulated_event(payload: EventCreate):
    """Sync callback required by the EventSource interface (it runs on a
    plain background thread, not the asyncio event loop) — dispatches into
    the single dedicated worker loop and blocks until it's done, same
    ordering as the old asyncio.run() call had."""
    loop = _get_worker_loop()
    future = asyncio.run_coroutine_threadsafe(_process_simulated_event(payload), loop)
    future.result()


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
