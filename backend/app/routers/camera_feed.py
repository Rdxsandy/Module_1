"""
routers/camera_feed.py

On-demand "active camera" AI pipeline: an operator either uploads a video
file, or points the AI at one registered camera's live RTSP stream, and it
runs through the RTSPEventSource -> local YOLO/EasyOCR ANPR pipeline.
Mirrors the threading / async-bridge pattern used by routers/simulator.py.

Only ONE feed (upload or live) ever runs at a time, by design — this is an
"AI magnifying glass" you point at whichever camera needs attention, not a
system that runs inference on every camera simultaneously. Running 30
YOLO+EasyOCR instances at once would exhaust a modest laptop's RAM/CPU long
before it exhausted the database connection pool; a VMS like Sentinel
already does the job of recording all 30 feeds continuously. Switching the
active camera safely stops the old pipeline (joins its threads, frees its
models) before starting the new one — see _stop_active_feed().
"""
import asyncio
import gc
import os
import threading
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, build_engine_and_sessionmaker
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.camera import Camera
from app.event_sources.rtsp_source import RTSPEventSource
from app.services.event_service import process_event
from app.services.vms_service import resolve_stream_url
from app.schemas.event import EventCreate

router = APIRouter(prefix="/api/camera-feed", tags=["camera-feed"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "videos")
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class AnalyzeCameraRequest(BaseModel):
    camera_id: str


# Global state for the single active video-feed source (by design: one
# feed at a time — see module docstring).
_feed_source: RTSPEventSource | None = None
_feed_thread: threading.Thread | None = None
is_running = False
_current_camera_id: str | None = None
_current_filename: str | None = None  # None while running == a live camera, not an upload
# Covers the window between "start accepted" and "_feed_source constructed"
# (model loading takes several seconds) — lets Stop clicked during that
# window still take effect instead of being silently swallowed.
_stop_requested = False

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
    if status == "reconnecting":
        # Not a processed frame — a live (RTSP/webcam) source dropped and
        # is retrying. Surface it in the activity log without touching
        # frame/detection counters or the last-known-good preview frame.
        _activity_log.appendleft({
            "time": now.isoformat(),
            "status": status,
            "plate": None,
            "confidence": None,
            "message": info.get("message"),
        })
        return

    _frames_processed += 1
    _last_frame_at = now
    _last_status = {**info, "time": now.isoformat()}
    if frame_bytes:
        _last_frame_bytes = frame_bytes
    if status == "detected":
        _plates_detected += 1

    # "streaming" fires on every AI-skipped frame (frame_skip throttling)
    # purely to keep the live preview flowing — logging each one would
    # flood the 30-entry activity log and bury real detections.
    if status == "streaming":
        return

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


def _run(camera_id: str, video_source: str):
    """Runs entirely off the request thread: constructing RTSPEventSource
    loads the YOLO + EasyOCR models (multi-second, first-run can also
    download weights), which would otherwise block the FastAPI event loop
    and blow past the frontend's request timeout."""
    global is_running, _feed_source
    try:
        source = RTSPEventSource(
            on_event=_on_feed_event,
            camera_id=camera_id,
            video_source=video_source,
            on_frame=_on_feed_frame,
        )
        _feed_source = source
        if _stop_requested:
            source.stop()
        source.start()
    except Exception as e:
        _on_feed_frame(None, {"status": "source_error", "message": str(e)})
    finally:
        is_running = False


def _stop_active_feed(timeout: float = 5.0) -> None:
    """Safely tear down whatever feed is currently running. Required before
    starting a new one: two overlapping YOLO+EasyOCR instances (old feed
    still shutting down, new one already loading models) is exactly what
    exhausts RAM on a modest box. Joins the old feed's thread — which in
    turn joins its own reader/exporter threads — before returning, then
    forces a GC pass so the freed model memory is actually reclaimed
    before the next feed loads its own copy."""
    global is_running, _feed_source, _feed_thread, _stop_requested
    _stop_requested = True
    if _feed_source:
        _feed_source.stop()
    if _feed_thread and _feed_thread.is_alive():
        _feed_thread.join(timeout=timeout)
    is_running = False
    _feed_source = None
    _feed_thread = None
    gc.collect()


@router.post("/upload")
async def upload_camera_feed(
    file: UploadFile = File(...),
    camera_id: str = Form("Camera-01"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Upload a video file and start streaming its frames to the ANPR
    pipeline. Switching from whatever feed (if any) was previously active
    happens automatically — see _stop_active_feed(). ADMIN only."""
    global _feed_source, _feed_thread, is_running, _current_camera_id, _current_filename, _stop_requested

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

    # Validation and file-save happen before this, so a bad request never
    # tears down a perfectly good running feed.
    _stop_active_feed()

    _reset_feed_stats()
    _stop_requested = False
    is_running = True
    _current_camera_id = camera_id
    _current_filename = file.filename

    _feed_thread = threading.Thread(target=_run, args=(camera_id, saved_path), daemon=True)
    _feed_thread.start()

    return {
        "status": "started",
        "camera_id": camera_id,
        "filename": file.filename,
        "mode": "file",
    }


@router.post("/analyze")
async def analyze_camera_feed(
    payload: AnalyzeCameraRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Point the AI pipeline at one registered camera's live stream — either
    its own manual stream_url, or a channel on the shared VMS (see
    app/services/vms_service.py). This is the "AI magnifying glass"
    endpoint: only one camera is ever actively analyzed at a time,
    switching safely stops whatever was running before. ADMIN only."""
    global _feed_source, _feed_thread, is_running, _current_camera_id, _current_filename, _stop_requested

    result = await db.execute(select(Camera).filter(Camera.name == payload.camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=400, detail=f"Camera '{payload.camera_id}' is not registered")
    stream_url = resolve_stream_url(camera)
    if not stream_url:
        raise HTTPException(
            status_code=400,
            detail=f"Camera '{payload.camera_id}' has no stream configured — set a stream URL or VMS channel from the Cameras page",
        )

    _stop_active_feed()

    _reset_feed_stats()
    _stop_requested = False
    is_running = True
    _current_camera_id = camera.name
    _current_filename = None  # None while running == a live camera, not an upload

    _feed_thread = threading.Thread(target=_run, args=(camera.name, stream_url), daemon=True)
    _feed_thread.start()

    return {
        "status": "started",
        "camera_id": camera.name,
        "mode": "live",
    }


@router.post("/stop")
def stop_camera_feed(
    user: User = Depends(require_admin),
):
    global _current_camera_id, _current_filename
    _stop_active_feed()
    _current_camera_id = None
    _current_filename = None
    return {"status": "stopped"}


@router.get("/status")
def get_camera_feed_status(
    _: User = Depends(get_current_user),
):
    mode = None
    if is_running:
        mode = "live" if _current_filename is None else "file"
    return {
        "running": is_running,
        "camera_id": _current_camera_id,
        "filename": _current_filename,
        "mode": mode,
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
