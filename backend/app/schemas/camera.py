"""schemas/camera.py — Pydantic models for Camera endpoints."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Camera-21"])
    department: str = Field(..., examples=["Traffic"])
    camera_type: str = Field(..., examples=["ANPR"])
    owner: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = Field(default="online", pattern="^(online|offline|maintenance)$")
    stream_url: Optional[str] = None


class CameraOut(CameraCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
