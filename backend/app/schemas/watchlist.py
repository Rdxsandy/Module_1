"""schemas/watchlist.py — Pydantic models for Watchlist endpoints."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=50, examples=["DL01AB1234"])
    entity_type: str = Field(default="VEHICLE", pattern="^(VEHICLE|PERSON)$", examples=["VEHICLE"])
    description: Optional[str] = None
    priority: str = Field(default="HIGH", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    active: bool = True
    metadata_json: Optional[Dict[str, Any]] = None


class WatchlistOut(WatchlistCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WatchlistLastSeen(BaseModel):
    camera_id: int
    camera_name: str
    latitude: float
    longitude: float
    event_time: datetime


class WatchlistLocationOut(BaseModel):
    id: int
    identifier: str
    entity_type: str
    description: Optional[str] = None
    priority: str
    last_seen: Optional[WatchlistLastSeen] = None

    model_config = {"from_attributes": True}
