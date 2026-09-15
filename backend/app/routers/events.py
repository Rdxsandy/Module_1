"""
routers/events.py - Vehicle event ingestion + search.

POST /api/events  - AUTHENTICATED (any user can submit events)
GET  /api/events  - AUTHENTICATED
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.event import EventCreate, EventOut
from app.schemas.alert import AlertOut
from app.services.event_service import process_event
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/events", tags=["events"])


class EventIngestResponse(EventOut):
    alert: Optional[AlertOut] = None


@router.post("", response_model=EventIngestResponse, status_code=201)
def ingest_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Ingest a vehicle detection event. Requires login."""
    try:
        event, alert = process_event(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = EventIngestResponse.model_validate(event)
    result.alert = AlertOut.model_validate(alert) if alert else None
    return result


@router.get("", response_model=list[EventOut])
def search_events(
    vehicle_number: Optional[str] = Query(None),
    camera_id: Optional[int] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Search events with optional filters. Requires login."""
    from app.models.vehicle_event import VehicleEvent
    from app.services.watchlist_service import normalize_vehicle_number

    q = db.query(VehicleEvent)
    if vehicle_number:
        q = q.filter(VehicleEvent.vehicle_number == normalize_vehicle_number(vehicle_number))
    if camera_id:
        q = q.filter(VehicleEvent.camera_id == camera_id)
    if start_time:
        q = q.filter(VehicleEvent.event_time >= start_time)
    if end_time:
        q = q.filter(VehicleEvent.event_time <= end_time)
    return q.order_by(VehicleEvent.event_time.desc()).limit(limit).all()
