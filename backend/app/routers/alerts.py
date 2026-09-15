"""
routers/alerts.py - Alerts endpoints.

GET   /api/alerts           - AUTHENTICATED
PATCH /api/alerts/{id}      - AUTHENTICATED
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status: Optional[str] = Query(None),
    vehicle_number: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return alerts ordered newest first. Requires login."""
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status.upper())
    if vehicle_number:
        from app.services.watchlist_service import normalize_vehicle_number
        q = q.filter(Alert.vehicle_number == normalize_vehicle_number(vehicle_number))
    return q.order_by(Alert.created_at.desc()).limit(limit).all()


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Acknowledge an alert. Requires login."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert
