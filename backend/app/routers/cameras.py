"""
routers/cameras.py - Camera registry endpoints + Bulk Upload.
"""
import io
import csv
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraOut
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

# Required fixed headers from spec
REQUIRED_HEADERS = [
    "name", "department", "camera_type", "owner", 
    "latitude", "longitude", "status", "stream_url", "description"
]

@router.get("/bulk-upload/template")
def download_template(_: User = Depends(get_current_user)):
    """Download the fixed CSV template for bulk upload."""
    content = ",".join(REQUIRED_HEADERS) + "\n"
    content += "CAM-001,Traffic,ANPR,Traffic Dept,28.6139,77.2090,ONLINE,,Main Road\n"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cameras_template.csv"}
    )

@router.post("/bulk-upload")
async def bulk_upload_cameras(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
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
    existing_names = {c[0] for c in db.query(Camera.name).all()}
    
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
            description = row.get("description", "").strip() or None
            
            cam = Camera(
                name=name,
                department=department,
                camera_type=camera_type,
                owner=owner,
                latitude=lat,
                longitude=lng,
                status=status,
                stream_url=stream_url,
                description=description
            )
            cameras_to_add.append(cam)
            existing_names.add(name) # Prevent duplicates within the same CSV
            
        except ValueError as e:
            failed += 1
            errors.append({"row": idx, "message": str(e)})
            
    if cameras_to_add:
        db.add_all(cameras_to_add)
        db.commit()
        imported = len(cameras_to_add)
        
    return {
        "total": total,
        "imported": imported,
        "failed": failed,
        "errors": errors
    }


@router.get("", response_model=list[CameraOut])
def list_cameras(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    camera_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by camera name"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return all cameras with optional filters. Requires login."""
    q = db.query(Camera)
    if department:
        q = q.filter(Camera.department == department)
    if status:
        q = q.filter(Camera.status == status)
    if camera_type:
        q = q.filter(Camera.camera_type == camera_type)
    if search:
        q = q.filter(Camera.name.ilike(f"%{search}%"))
    return q.order_by(Camera.id).all()

@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Onboard a new camera. ADMIN only."""
    camera = Camera(**payload.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera

@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera
