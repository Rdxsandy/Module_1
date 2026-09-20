"""
routers/camera_feed.py

Lets an operator upload a video file from the dashboard and run it through
the RTSPEventSource -> Colab ANPR pipeline, exactly like a real camera feed.
Mirrors the threading / async-bridge pattern used by routers/simulator.py.
"""
import asyncio
import os
import threading
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, build_engine_and_sessionmaker
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.camera import Camera
from app.event_sources.rtsp_source import RTSPEventSource
from app.services.event_service import process_event
from app.schemas.event import EventCreate

router = APIRouter(prefix="/api/camera-feed", tags=["camera-feed"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "videos")
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Global state for the single active video-feed source (PoC: one feed at a time)
_feed_source: RTSPEventSource | None = None
is_running = False
_current_camera_id: str | None = None
_current_filename: str | None = None

# Live-monitoring state — lets the frontend confirm frames are actually
# flowing through the AI pipeline (not just that the upload succeeded).
_started_at: datetime | None = None
_frames_processed = 0
_plates_detected = 0
_last_frame_at: datetime | None = None
_last_frame_bytes: bytes | None = None
_last_status: dict | None = None
_source_error: str | None = None
_activity_log: deque = deque(maxlen=30)


def _reset_feed_stats():
    global _started_at, _frames_processed, _plates_detected, _last_frame_at
    global _last_frame_bytes, _last_status, _source_error
    _started_at = datetime.now(timezone.utc)
    _frames_processed = 0
    _plates_detected = 0
    _last_frame_at = None
    _last_frame_bytes = None
    _last_status = None
    _source_error = None
    _activity_log.clear()


def _on_feed_frame(frame_bytes: bytes | None, info: dict):
    """Sync callback from RTSPEventSource — fires for every processed frame,
    detection or not, so the feed page can show the pipeline is alive."""
    global _frames_processed, _plates_detected, _last_frame_at, _last_frame_bytes
    global _last_status, _source_error

    status = info.get("status")
    now = datetime.now(timezone.utc)

    if status == "source_error":
        _source_error = info.get("message")
        return
    if status == "ended":
        return

    _frames_processed += 1
    _last_frame_at = now
    _last_status = {**info, "time": now.isoformat()}
    if frame_bytes:
        _last_frame_bytes = frame_bytes
    if status == "detected":
        _plates_detected += 1

    _activity_log.appendleft({
        "time": now.isoformat(),
        "status": status,
        "plate": info.get("plate"),
        "confidence": info.get("confidence"),
        "message": info.get("message"),
    })


async def _process_feed_event(payload: EventCreate):
    """Each event gets its own short-lived session — safe across the
    background feed thread without holding a session open for the whole run."""
    _, feed_session_local = _get_worker_db()
    async with feed_session_local() as db:
        try:
            await process_event(db, payload)
        except Exception as e:
            print(f"Camera feed error processing event: {e}")
            _activity_log.appendleft({
                "time": datetime.now(timezone.utc).isoformat(),
                "status": "event_error",
                "plate": payload.vehicle_number,
                "confidence": payload.confidence,
                "message": f"Failed to save event/check watchlist: {e}",
            })


# One dedicated event loop for the feed thread, started lazily and reused for
# every event — NOT asyncio.run() per call, which creates and tears down a
# brand-new loop each time. That loop also gets its OWN engine/sessionmaker
# (never the app's main `engine`/`SessionLocal`): asyncpg connections are
# bound to the loop that opened them, so sharing one pool across two loops
# raises "Future attached to a different loop" / "Event loop is closed" on
# whichever request loses the race for a cross-loop connection.
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
                target=_worker_loop.run_forever, daemon=True, name="camera-feed-worker-loop",
            )
            _worker_loop_thread.start()
        return _worker_loop


def _get_worker_db():
    """The camera-feed worker loop's own engine/sessionmaker — separate pool
    from app.database.engine, since that one belongs to the main FastAPI loop."""
    global _worker_engine, _worker_session_local
    with _worker_loop_lock:
        if _worker_engine is None:
            _worker_engine, _worker_session_local = build_engine_and_sessionmaker(
                pool_size=2, max_overflow=3
            )
        return _worker_engine, _worker_session_local


def _on_feed_event(payload: EventCreate):
    """Sync callback required by the EventSource interface (runs on a plain
    background thread, not the asyncio event loop) — dispatches into the
    single dedicated worker loop and blocks until it's done, same ordering
    as the old asyncio.run() call had."""
    loop = _get_worker_loop()
    future = asyncio.run_coroutine_threadsafe(_process_feed_event(payload), loop)
    future.result()


def _run(source: RTSPEventSource):
    global is_running
    try:
        source.start()
    finally:
        is_running = False


@router.post("/upload")
async def upload_camera_feed(
    file: UploadFile = File(...),
    camera_id: str = Form("Camera-01"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Upload a video file and start streaming its frames to the ANPR pipeline. ADMIN only."""
    global _feed_source, is_running, _current_camera_id, _current_filename

    if is_running:
        raise HTTPException(status_code=400, detail="A video feed is already running — stop it first")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    result = await db.execute(select(Camera).filter(Camera.name == camera_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Camera '{camera_id}' is not registered")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)

    contents = await file.read()
    with open(saved_path, "wb") as f:
        f.write(contents)

    _reset_feed_stats()
    _feed_source = RTSPEventSource(
        on_event=_on_feed_event,
        camera_id=camera_id,
        video_source=saved_path,
        on_frame=_on_feed_frame,
    )
    is_running = True
    _current_camera_id = camera_id
    _current_filename = file.filename

    thread = threading.Thread(target=_run, args=(_feed_source,), daemon=True)
    thread.start()

    return {
        "status": "started",
        "camera_id": camera_id,
        "filename": file.filename,
    }


@router.post("/stop")
def stop_camera_feed(
    user: User = Depends(require_admin),
):
    global is_running, _feed_source, _current_camera_id, _current_filename
    if _feed_source:
        _feed_source.stop()
    is_running = False
    _current_camera_id = None
    _current_filename = None
    return {"status": "stopped"}


@router.get("/status")
def get_camera_feed_status(
    _: User = Depends(get_current_user),
):
    return {
        "running": is_running,
        "camera_id": _current_camera_id,
        "filename": _current_filename,
        "started_at": _started_at.isoformat() if _started_at else None,
        "frames_processed": _frames_processed,
        "plates_detected": _plates_detected,
        "last_frame_at": _last_frame_at.isoformat() if _last_frame_at else None,
        "last_status": _last_status,
        "source_error": _source_error,
        "has_preview": _last_frame_bytes is not None,
    }


@router.get("/activity")
def get_camera_feed_activity(
    _: User = Depends(get_current_user),
):
    """Recent frame-processing results (detections and misses alike) as a
    live log, newest first."""
    return {"items": list(_activity_log)}


async def frame_generator():
    """Yield the latest processed frame as a multipart/x-mixed-replace part,
    forever, at ~10 fps. Re-sends the same frame between detections so the
    stream never stalls even while the pipeline waits on the ANPR service."""
    while True:
        if _last_frame_bytes:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + _last_frame_bytes + b'\r\n'
            )
        await asyncio.sleep(0.1)


# No auth dependency: a plain <img> tag can't attach an Authorization header,
# so this mirrors how browsers consume any other MJPEG camera endpoint. Only
# the latest already-processed frame is exposed, nothing else in the API.
@router.get("/stream")
async def stream_camera_feed():
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
