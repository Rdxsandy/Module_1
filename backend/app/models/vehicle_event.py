"""
models/vehicle_event.py — VehicleEvent ORM model.
Canonical domain event: one detection of one vehicle by one camera.
The POST /api/events endpoint produces these records.
A future real RTSP/ANPR adapter will POST the same schema.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class VehicleEvent(Base):
    __tablename__ = "vehicle_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    vehicle_number = Column(String(50), nullable=False, index=True)  # normalised
    event_time = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True, default=1.0)
    event_type = Column(String(50), nullable=False, default="ANPR")
    # raw_payload stores the original request body as JSON text (JSONB in PostgreSQL)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    camera = relationship("Camera", backref="events")
    alerts = relationship("Alert", back_populates="event")
