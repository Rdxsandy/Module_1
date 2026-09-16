"""
routers/alerts.py - Alerts endpoints.

GET   /api/alerts           - AUTHENTICATED
PATCH /api/alerts/{id}      - AUTHENTICATED
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    status: Optional[str] = Query(None),
    vehicle_number: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return alerts ordered newest first. Requires login."""
    q = select(Alert)
    if status:
        q = q.filter(Alert.status == status.upper())
    if vehicle_number:
        from app.services.watchlist_service import normalize_vehicle_number
        q = q.filter(Alert.vehicle_number == normalize_vehicle_number(vehicle_number))
    result = await db.execute(q.order_by(Alert.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Alert).filter(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Acknowledge an alert. Requires login."""
    result = await db.execute(select(Alert).filter(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)
    await log_audit(db, user, "ACKNOWLEDGE", "ALERT", str(alert_id), None)
    return alert

@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Resolve an alert. Requires login."""
    result = await db.execute(select(Alert).filter(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "RESOLVED"
    await db.commit()
    await db.refresh(alert)
    await log_audit(db, user, "RESOLVE", "ALERT", str(alert_id), None)
    return alert
