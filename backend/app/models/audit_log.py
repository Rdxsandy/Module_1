from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # e.g., "CREATE_CAMERA", "ACKNOWLEDGE_ALERT"
    entity_type = Column(String(50), nullable=False) # e.g., "CAMERA", "ALERT", "WATCHLIST"
    entity_id = Column(String(50), nullable=True) 
    details = Column(JSON, nullable=True) # Any additional context
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
