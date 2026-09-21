"""
routers/cameras.py - Camera registry endpoints + Bulk Upload.
"""
import asyncio
import io
import csv
import cv2
from datetime import date, datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.vms_service import resolve_stream_url, get_vms_config
from app.routers import camera_feed as camera_feed_module

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _serialize_camera(camera: Camera, viewer: User) -> dict:
    """Builds the API-facing camera dict. stream_url may embed
    rtsp://user:pass@... credentials, so only an ADMIN viewer (who can
    already edit it) gets the raw value back — everyone else gets
    has_stream, which is all the UI needs to decide whether Analyze /
    live-thumbnail features are available for this camera."""
    is_admin = viewer.role == "ADMIN"
    return {
        "id": camera.id,
        "name": camera.name,
        "department": camera.department,
        "camera_type": camera.camera_type,
        "owner": camera.owner,
        "latitude": camera.latitude,
        "longitude": camera.longitude,
        "status": camera.status,
        "stream_url": camera.stream_url if is_admin else None,
        "vms_channel": camera.vms_channel,
        "has_stream": resolve_stream_url(camera) is not None,
        "vms_type": camera.vms_type,
        "vendor": camera.vendor,
        "storage_type": camera.storage_type,
        "retention_days": camera.retention_days,
        "description": camera.description,
        "installation_date": camera.installation_date,
        "last_maintenance_date": camera.last_maintenance_date,
        "coverage_radius_meters": camera.coverage_radius_meters,
        "created_at": camera.created_at,
        "updated_at": camera.updated_at,
        "last_seen_at": camera.last_seen_at,
    }

# Required fixed headers from spec
REQUIRED_HEADERS = [
    "name", "department", "camera_type", "owner", 
    "latitude", "longitude", "status", "stream_url",
    "vms_type", "vendor", "storage_type", "retention_days", "description"
]

@router.get("/bulk-upload/template")
def download_template(_: User = Depends(get_current_user)):
    """Download the fixed CSV template for bulk upload."""
    content = ",".join(REQUIRED_HEADERS) + "\n"
    content += "CAM-001,Traffic,ANPR,Traffic Dept,28.6139,77.2090,ONLINE,,,,,,Main Road\n"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cameras_template.csv"}
    )

@router.post("/bulk-upload")
async def bulk_upload_cameras(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Parse, validate and bulk insert cameras from CSV. ADMIN only.
    Return total, imported, failed and array of row-level errors.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    
    content = await file.read()
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.")
    
    reader = csv.DictReader(io.StringIO(decoded))
    
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file is empty or missing headers.")
        
    # Check headers (allow extra, but must have all required)
    missing = set(REQUIRED_HEADERS) - set(reader.fieldnames)
    if missing:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required headers: {', '.join(missing)}"
        )
        
    total = 0
    imported = 0
    failed = 0
    errors = []
    
    # Pre-fetch existing names to check for duplicates in memory
    existing_result = await db.execute(select(Camera.name))
    existing_names = {row[0] for row in existing_result.all()}
    
    cameras_to_add = []

    for idx, row in enumerate(reader, start=2): # Start=2 because row 1 is header
        total += 1
        
        # Skip completely empty rows
        if not any(row.values()):
            continue
            
        try:
            name = row.get("name", "").strip()
            if not name:
                raise ValueError("Name cannot be empty")
            if name in existing_names:
                raise ValueError("Duplicate camera name")
                
            department = row.get("department", "").strip()
            if not department:
                raise ValueError("Department cannot be empty")
                
            camera_type = row.get("camera_type", "").strip()
            if not camera_type:
                raise ValueError("Camera type cannot be empty")
                
            owner = row.get("owner", "").strip()
            if not owner:
                raise ValueError("Owner cannot be empty")
                
            try:
                lat = float(row.get("latitude", ""))
                if not (-90 <= lat <= 90):
                    raise ValueError
            except:
                raise ValueError("Invalid latitude")
                
            try:
                lng = float(row.get("longitude", ""))
                if not (-180 <= lng <= 180):
                    raise ValueError
            except:
                raise ValueError("Invalid longitude")
                
            status = row.get("status", "").strip().lower()
            if status not in ["online", "offline", "maintenance"]:
                raise ValueError("Status must be ONLINE, OFFLINE, or MAINTENANCE")
                
            stream_url = row.get("stream_url", "").strip() or None
            vms_type = row.get("vms_type", "").strip() or None
            vendor = row.get("vendor", "").strip() or None
            storage_type = row.get("storage_type", "").strip() or None
            
            try:
                rd_str = row.get("retention_days", "").strip()
                retention_days = int(rd_str) if rd_str else None
            except:
                raise ValueError("Invalid retention_days")

            description = row.get("description", "").strip() or None
            
            cam = Camera(
                name=name,
                department=department,
                camera_type=camera_type,
                owner=owner,
                latitude=lat,
                longitude=lng,
                status=status.upper(),
                stream_url=stream_url,
                vms_type=vms_type,
                vendor=vendor,
                storage_type=storage_type,
                retention_days=retention_days,
                description=description
            )
            cameras_to_add.append(cam)
            existing_names.add(name) # Prevent duplicates within the same CSV
            
        except ValueError as e:
            failed += 1
            errors.append({"row": idx, "message": str(e)})
            
    if cameras_to_add:
        db.add_all(cameras_to_add)
        await db.commit()
        imported = len(cameras_to_add)
        await log_audit(db, user, "BULK_IMPORT", "CAMERA", None, {"imported": imported, "failed": failed})
        
    return {
        "total": total,
        "imported": imported,
        "failed": failed,
        "errors": errors
    }


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    camera_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by camera name"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all cameras with optional filters. Requires login."""
    q = select(Camera)
    if department:
        q = q.filter(Camera.department == department)
    if status:
        q = q.filter(Camera.status == status)
    if camera_type:
        q = q.filter(Camera.camera_type == camera_type)
    if search:
        q = q.filter(Camera.name.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(Camera.id))
    return [_serialize_camera(c, user) for c in result.scalars().all()]

@router.get("/vms-config")
def get_vms_configuration(_: User = Depends(get_current_user)):
    """Whether shared VMS credentials are configured (VMS_HOST in .env) and
    how many channels it exposes — lets the frontend show the channel
    picker only when it's actually usable. Never includes the credentials."""
    return get_vms_config()

@router.post("", response_model=CameraOut, status_code=201)
async def create_camera(
    payload: CameraCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Onboard a new camera. ADMIN only."""
    result = await db.execute(select(Camera).filter(Camera.name == payload.name))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A camera named '{payload.name}' already exists.",
        )

    camera = Camera(**payload.model_dump())
    db.add(camera)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A camera named '{payload.name}' already exists.",
        )
    await db.refresh(camera)
    await log_audit(db, user, "CREATE", "CAMERA", camera.name, payload.model_dump())
    return _serialize_camera(camera, user)

@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Edit an existing camera — only the fields provided are changed.
    Typical use: set stream_url (a standalone camera's own RTSP URL) or
    vms_channel (which channel on the shared VMS this maps to; see
    GET /vms-config and backend/.env's VMS_* vars). ADMIN only."""
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != camera.name:
        dup = await db.execute(select(Camera).filter(Camera.name == updates["name"]))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"A camera named '{updates['name']}' already exists.")

    for field, value in updates.items():
        setattr(camera, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A camera with that name already exists.")
    await db.refresh(camera)
    await log_audit(db, user, "UPDATE", "CAMERA", camera.name, updates)
    return _serialize_camera(camera, user)

@router.get("/gap-analysis")
async def gap_analysis(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Sample gap-analysis report for Model 1: ageing infrastructure and
    maintenance backlog across the camera registry.

    - Ageing: installation_date older than 5 years -> "Requires Upgrade"
    - Maintenance: status OFFLINE, or last_maintenance_date older than
      1 year (or never recorded) -> "Requires Maintenance"
    """
    today = date.today()
    ageing_cutoff = today - timedelta(days=365 * 5)
    maintenance_cutoff = today - timedelta(days=365)

    total_result = await db.execute(select(Camera))
    all_cameras = total_result.scalars().all()
    total_cameras = len(all_cameras)

    ageing_cameras = [
        c for c in all_cameras
        if c.installation_date is not None and c.installation_date < ageing_cutoff
    ]

    maintenance_cameras = [
        c for c in all_cameras
        if c.status == "OFFLINE"
        or c.last_maintenance_date is None
        or c.last_maintenance_date < maintenance_cutoff
    ]

    offline_cameras = [c for c in all_cameras if c.status == "OFFLINE"]

    def _summarize(cam: Camera) -> dict:
        return {
            "id": cam.id,
            "name": cam.name,
            "department": cam.department,
            "status": cam.status,
            "installation_date": cam.installation_date.isoformat() if cam.installation_date else None,
            "last_maintenance_date": cam.last_maintenance_date.isoformat() if cam.last_maintenance_date else None,
        }

    def _pct(count: int) -> float:
        return round((count / total_cameras) * 100, 1) if total_cameras else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cameras": total_cameras,
        "ageing": {
            "requires_upgrade_count": len(ageing_cameras),
            "requires_upgrade_pct": _pct(len(ageing_cameras)),
            "cameras": [_summarize(c) for c in ageing_cameras],
        },
        "maintenance": {
            "requires_maintenance_count": len(maintenance_cameras),
            "requires_maintenance_pct": _pct(len(maintenance_cameras)),
            "offline_count": len(offline_cameras),
            "cameras": [_summarize(c) for c in maintenance_cameras],
        },
    }


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _serialize_camera(camera, user)


# Bounded so a dead/unreachable camera doesn't tie up a thread-pool worker
# for the OS default (which can be tens of seconds — see rtsp_source.py's
# CAP_PROP_OPEN_TIMEOUT_MSEC comment for how this was discovered).
_SNAPSHOT_TIMEOUT_MS = 4000


def _grab_snapshot_sync(stream_url: str) -> bytes | None:
    """Opens the stream just long enough to grab and JPEG-encode one frame.
    Blocking native I/O — always called via asyncio.to_thread, never awaited
    directly on the event loop."""
    is_rtsp = stream_url.lower().startswith("rtsp://")
    if is_rtsp:
        cap = cv2.VideoCapture(
            stream_url, cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, _SNAPSHOT_TIMEOUT_MS,
             cv2.CAP_PROP_READ_TIMEOUT_MSEC, _SNAPSHOT_TIMEOUT_MS],
        )
    else:
        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
    try:
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        if not ret:
            return None
        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()
    finally:
        cap.release()


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """A single still JPEG from a camera's stream, for the grid dashboard's
    periodic thumbnails — deliberately NOT a live video feed; that's what
    /api/camera-feed's single active-camera pipeline is for. Pulling a
    still every ~10s per camera is what actually scales to 30 cameras on
    modest hardware, per the "AI magnifying glass" design."""
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    stream_url = resolve_stream_url(camera)
    if not stream_url:
        raise HTTPException(status_code=404, detail="Camera has no stream configured")

    # If this camera is the one currently under full AI analysis, reuse its
    # already-decoded frame instead of opening a second connection to the
    # same stream — some camera firmware caps concurrent RTSP clients, and
    # it's free (already sitting in memory).
    if (
        camera_feed_module._current_camera_id == camera.name
        and camera_feed_module._last_frame_bytes
    ):
        return Response(content=camera_feed_module._last_frame_bytes, media_type="image/jpeg")

    frame_bytes = await asyncio.to_thread(_grab_snapshot_sync, stream_url)
    if frame_bytes is None:
        raise HTTPException(status_code=503, detail="Could not reach camera stream")
    return Response(content=frame_bytes, media_type="image/jpeg")
