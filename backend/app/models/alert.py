"""
models/alert.py — Alert ORM model.
Created automatically when a VehicleEvent's vehicle_number matches an active
watchlist entry.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("vehicle_events.id"), nullable=False)
    watchlist_id = Column(Integer, ForeignKey("watchlist.id"), nullable=False)
    vehicle_number = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="high")
    message = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="NEW", index=True)  # NEW/ACKNOWLEDGED/RESOLVED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    acknowledged_at = Column(DateTime, nullable=True)

    # Relationships
    event = relationship("VehicleEvent", back_populates="alerts")
    watchlist_entry = relationship("Watchlist", backref="alerts")
