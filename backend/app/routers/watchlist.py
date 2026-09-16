"""
routers/watchlist.py - Watchlist management endpoints.

GET    /api/watchlist       - AUTHENTICATED
POST   /api/watchlist       - ADMIN ONLY
DELETE /api/watchlist/{id}  - ADMIN ONLY
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.watchlist import Watchlist
from app.schemas.watchlist import WatchlistCreate, WatchlistOut
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
