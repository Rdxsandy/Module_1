"""
services/event_service.py

Orchestrates the canonical event ingestion flow (spec §7 backend behaviour):
  1. Validate camera_id
  2. Insert vehicle_event (with normalised plate)
  3. Query active watchlist for a match
  4. If match → create alert
  5. Return (event, alert_or_None)

This service is the single authoritative place for the event→alert pipeline.
Routers, mock generators and future real adapters all go through here.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.models.vehicle_event import VehicleEvent
from app.models.alert import Alert
from app.schemas.event import EventCreate
from app.services.watchlist_service import match_watchlist, normalize_vehicle_number


async def process_event(
    db: AsyncSession,
    payload: EventCreate,
) -> tuple[VehicleEvent, Alert | None]:
    """
    Persist a vehicle detection event and, if the plate is on the watchlist,
    auto-create an alert.

    Raises ValueError if camera_id does not exist.
    """
    # --- 1. Validate camera ---
    result = await db.execute(select(Camera).filter(Camera.name == payload.camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise ValueError(f"Camera name '{payload.camera_id}' not found")

    # --- 2. Normalise and insert event ---
    normalised_plate = normalize_vehicle_number(payload.vehicle_number)
    event = VehicleEvent(
        camera_id=camera.id,
        vehicle_number=normalised_plate,
        event_time=payload.event_time,
        latitude=payload.latitude,
        longitude=payload.longitude,
        confidence=payload.confidence,
        event_type=payload.event_type,
        raw_payload=json.dumps(payload.model_dump(mode="json")),
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()  # get event.id before committing

    # --- 3. Watchlist match ---
    wl_entry = await match_watchlist(db, normalised_plate)

    # --- 4. Create alert if matched ---
    alert: Alert | None = None
    if wl_entry:
        alert = Alert(
            event_id=event.id,
            watchlist_id=wl_entry.id,
            vehicle_number=normalised_plate,
            severity=wl_entry.priority,
            message=(
                f"Watchlist hit: {wl_entry.entity_type} — "
                f"{wl_entry.description or 'No description'} "
                f"detected by {camera.name} at {payload.event_time.isoformat()}"
            ),
            status="NEW",
            created_at=datetime.now(timezone.utc),
        )
        db.add(alert)

    await db.commit()
    await db.refresh(event)
    if alert:
        await db.refresh(alert)

    return event, alert
