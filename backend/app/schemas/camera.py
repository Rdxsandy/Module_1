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
    # Manual RTSP URL for a standalone camera (may embed its own
    # rtsp://user:pass@... credentials). For a shared multi-channel VMS,
    # use vms_channel instead — see app/services/vms_service.py.
    stream_url: Optional[str] = None
    # Which channel (1..N) on the shared VMS (configured once via VMS_* env
    # vars) this camera maps to. Takes priority over stream_url when set.
    vms_channel: Optional[int] = Field(default=None, ge=1)
    vms_type: Optional[str] = None
    vendor: Optional[str] = None
    storage_type: Optional[str] = None
    retention_days: Optional[int] = None
    description: Optional[str] = None
    installation_date: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    coverage_radius_meters: int = Field(default=50, ge=0)


class CameraUpdate(BaseModel):
    """All fields optional — PATCH only applies what's provided."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    department: Optional[str] = None
    camera_type: Optional[str] = None
    owner: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    status: Optional[str] = Field(default=None, pattern="^(ONLINE|OFFLINE|MAINTENANCE)$")
    stream_url: Optional[str] = None
    vms_channel: Optional[int] = Field(default=None, ge=1)
    vms_type: Optional[str] = None
    vendor: Optional[str] = None
    storage_type: Optional[str] = None
    retention_days: Optional[int] = None
    description: Optional[str] = None
    installation_date: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    coverage_radius_meters: Optional[int] = Field(default=None, ge=0)


class CameraOut(CameraCreate):
    id: int
    # True if this camera resolves to a usable stream (either vms_channel
    # + a configured VMS, or a manual stream_url) — the UI's signal for
    # whether Analyze/live-thumbnail features are available. stream_url
    # itself is only populated for ADMIN viewers (see routers/cameras.py):
    # it may embed rtsp://user:pass@... credentials that must not leak to
    # every logged-in user via this list/detail response.
    has_stream: bool = False
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
