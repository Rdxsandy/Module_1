"""schemas/camera.py — Pydantic models for Camera endpoints."""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Camera-21"])
    department: str = Field(..., examples=["Traffic"])
    camera_type: str = Field(..., examples=["ANPR"])
    owner: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = Field(default="ONLINE", pattern="^(ONLINE|OFFLINE|MAINTENANCE)$")
    stream_url: Optional[str] = None
    vms_type: Optional[str] = None
    vendor: Optional[str] = None
    storage_type: Optional[str] = None
    retention_days: Optional[int] = None
    description: Optional[str] = None
    installation_date: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    coverage_radius_meters: int = Field(default=50, ge=0)


class CameraOut(CameraCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
