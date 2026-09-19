"""
routers/watchlist.py - Watchlist management endpoints.

GET    /api/watchlist       - AUTHENTICATED
POST   /api/watchlist       - ADMIN ONLY
DELETE /api/watchlist/{id}  - ADMIN ONLY
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.watchlist import Watchlist
from app.models.vehicle_event import VehicleEvent
from app.schemas.watchlist import WatchlistCreate, WatchlistOut, WatchlistLastSeen, WatchlistLocationOut
from app.services.watchlist_service import normalize_vehicle_number
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistOut])
async def list_watchlist(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all watchlist entries. Requires login."""
    result = await db.execute(select(Watchlist).order_by(Watchlist.id))
    return result.scalars().all()


@router.get("/locations", response_model=list[WatchlistLocationOut])
async def get_watchlist_locations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Last known location (from its most recent detection) of every active
    watchlist entry, for auto-plotting on the GIS map without searching each
    plate individually. Entries never detected are returned with last_seen=null."""
    wl_result = await db.execute(select(Watchlist).filter(Watchlist.active.is_(True)))
    entries = wl_result.scalars().all()

    items = []
    for entry in entries:
        ev_result = await db.execute(
            select(VehicleEvent)
            .options(joinedload(VehicleEvent.camera))
            .filter(VehicleEvent.vehicle_number == entry.identifier)
            .order_by(VehicleEvent.event_time.desc())
            .limit(1)
        )
        last_event = ev_result.unique().scalar_one_or_none()
        items.append(WatchlistLocationOut(
            id=entry.id,
            identifier=entry.identifier,
            entity_type=entry.entity_type,
            description=entry.description,
            priority=entry.priority,
            last_seen=WatchlistLastSeen(
                camera_id=last_event.camera_id,
                camera_name=last_event.camera.name if last_event.camera else f"Camera-{last_event.camera_id}",
                latitude=last_event.latitude,
                longitude=last_event.longitude,
                event_time=last_event.event_time,
            ) if last_event else None,
        ))
    return items


@router.post("", response_model=WatchlistOut, status_code=201)
async def add_to_watchlist(
    payload: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),   # ADMIN ONLY
):
    """Add to watchlist. ADMIN only."""
    normalised = normalize_vehicle_number(payload.identifier)
    result = await db.execute(select(Watchlist).filter(Watchlist.identifier == normalised))
    existing = result.scalar_one_or_none()
    if existing:
        existing.active = payload.active
        existing.priority = payload.priority
        existing.description = payload.description
        existing.metadata_json = payload.metadata_json
        await db.commit()
        await db.refresh(existing)
        await log_audit(db, user, "UPDATE", "WATCHLIST", normalised, payload.model_dump())
        return existing
    entry = Watchlist(**{**payload.model_dump(), "identifier": normalised})
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await log_audit(db, user, "CREATE", "WATCHLIST", normalised, payload.model_dump())
    return entry


@router.delete("/{entry_id}", status_code=204)
async def remove_from_watchlist(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),   # ADMIN ONLY
):
    """Soft-delete from watchlist. ADMIN only."""
    result = await db.execute(select(Watchlist).filter(Watchlist.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    entry.active = False
    await db.commit()
    await log_audit(db, user, "DELETE", "WATCHLIST", entry.identifier, None)
