"""
routers/cameras.py - Camera registry endpoints + Bulk Upload.
"""
import io
import csv
from datetime import date, datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraOut
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

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
    _: User = Depends(get_current_user),
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
    return result.scalars().all()

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
    return camera

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
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera
