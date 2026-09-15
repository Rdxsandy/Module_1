"""schemas/alert.py — Pydantic models for Alert endpoints."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    event_id: int
    watchlist_id: int
    vehicle_number: str
    severity: str
    message: str
    status: str
    created_at: datetime
    acknowledged_at: Optional[datetime]

    model_config = {"from_attributes": True}
