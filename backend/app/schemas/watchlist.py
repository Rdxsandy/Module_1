"""schemas/watchlist.py — Pydantic models for Watchlist endpoints."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    vehicle_number: str = Field(..., min_length=1, max_length=50, examples=["DL01AB1234"])
    entity_type: str = Field(default="stolen_vehicle", examples=["stolen_vehicle"])
    description: Optional[str] = None
    priority: str = Field(default="high", pattern="^(low|medium|high|critical)$")
    active: bool = True


class WatchlistOut(WatchlistCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
