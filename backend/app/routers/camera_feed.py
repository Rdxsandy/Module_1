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

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, SessionLocal
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


async def _process_feed_event(payload: EventCreate):
    """Each event gets its own short-lived session — safe across the
    background feed thread without holding a session open for the whole run."""
    async with SessionLocal() as db:
        try:
            await process_event(db, payload)
        except Exception as e:
            print(f"Camera feed error processing event: {e}")


def _on_feed_event(payload: EventCreate):
    """Sync callback required by the EventSource interface (runs on a plain
    background thread, not the asyncio event loop) — bridges into the async
    DB session with its own event loop."""
    asyncio.run(_process_feed_event(payload))


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

    _feed_source = RTSPEventSource(
        on_event=_on_feed_event,
        camera_id=camera_id,
        video_source=saved_path,
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
    }
