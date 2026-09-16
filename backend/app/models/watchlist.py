"""
models/watchlist.py — Watchlist ORM model.
Stores vehicle registrations (or other entities) that should trigger alerts
when detected by any camera.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String(50), unique=True, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, default="VEHICLE") # VEHICLE | PERSON
    description = Column(String(500), nullable=True)
    priority = Column(String(20), nullable=False, default="HIGH")  # LOW | MEDIUM | HIGH | CRITICAL
    active = Column(Boolean, nullable=False, default=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
