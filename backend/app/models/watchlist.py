"""
models/watchlist.py — Watchlist ORM model.
Stores vehicle registrations (or other entities) that should trigger alerts
when detected by any camera.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    # Stored normalised (upper-case, alphanumeric only) for fast exact matching
    vehicle_number = Column(String(50), unique=True, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, default="stolen_vehicle")
    description = Column(String(500), nullable=True)
    priority = Column(String(20), nullable=False, default="high")  # low/medium/high/critical
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
