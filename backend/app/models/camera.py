"""
models/camera.py — Camera ORM model.
Represents a physical CCTV camera onboarded into the central registry.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    department = Column(String(100), nullable=False, index=True)
    camera_type = Column(String(50), nullable=False)   # ANPR / Fixed / PTZ
    owner = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default="ONLINE", index=True)
    stream_url = Column(String(500), nullable=True)
    vms_type = Column(String(50), nullable=True)
    vendor = Column(String(50), nullable=True)
    storage_type = Column(String(50), nullable=True)
    retention_days = Column(Integer, nullable=True)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_seen_at = Column(DateTime, nullable=True)
