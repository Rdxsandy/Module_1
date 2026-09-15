"""schemas/event.py — Pydantic models for VehicleEvent endpoints."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


from typing import Optional, Dict, Any

class EventCreate(BaseModel):
    camera_id: str = Field(..., examples=["CAM-001"])
    vehicle_number: str = Field(..., min_length=1, max_length=50, examples=["DL01AB1234"])
    event_time: datetime
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    event_type: str = Field(default="ANPR", examples=["ANPR"])
    attributes: Optional[Dict[str, Any]] = None
    source: Optional[Dict[str, Any]] = None


class EventOut(BaseModel):
    id: int
    camera_id: int
    vehicle_number: str
    event_time: datetime
    latitude: float
    longitude: float
    confidence: Optional[float]
    event_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VehicleHistoryItem(BaseModel):
    camera_id: int
    camera_name: str
    event_time: datetime
    latitude: float
    longitude: float
    confidence: Optional[float]

    model_config = {"from_attributes": True}


class VehicleHistoryOut(BaseModel):
    vehicle_number: str
    history: list[VehicleHistoryItem]
    watchlist_status: Optional[str] = None   # priority if on watchlist
    watchlist_reason: Optional[str] = None   # description if on watchlist
