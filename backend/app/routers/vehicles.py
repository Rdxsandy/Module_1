"""
routers/vehicles.py - Vehicle history endpoint.

GET /api/vehicles/{vehicle_number}/history - AUTHENTICATED
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.vehicle_event import VehicleEvent
from app.schemas.event import VehicleHistoryItem, VehicleHistoryOut
from app.services.watchlist_service import normalize_vehicle_number, match_watchlist
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.get("/{vehicle_number}/history", response_model=VehicleHistoryOut)
def get_vehicle_history(
    vehicle_number: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return ordered movement history for a vehicle. Requires login."""
    normalised = normalize_vehicle_number(vehicle_number)

    events = (
        db.query(VehicleEvent)
        .options(joinedload(VehicleEvent.camera))
        .filter(VehicleEvent.vehicle_number == normalised)
        .order_by(VehicleEvent.event_time.asc())
        .all()
    )

    history = [
        VehicleHistoryItem(
            camera_id=e.camera_id,
            camera_name=e.camera.name if e.camera else f"Camera-{e.camera_id}",
            event_time=e.event_time,
            latitude=e.latitude,
            longitude=e.longitude,
            confidence=e.confidence,
        )
        for e in events
    ]

    wl = match_watchlist(db, normalised)

    return VehicleHistoryOut(
        vehicle_number=normalised,
        history=history,
        watchlist_status=wl.priority if wl else None,
        watchlist_reason=wl.description if wl else None,
    )
