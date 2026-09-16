"""
services/watchlist_service.py

Handles vehicle-number normalisation and active watchlist lookup.
Normalisation rule (from spec §8): upper-case, alphanumeric characters only.
Exact matching only in PoC — no fuzzy matching.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.watchlist import Watchlist


def normalize_vehicle_number(value: str) -> str:
    """Strip spaces/hyphens, force upper-case.
    'dl 01 ab 1234', 'DL-01-AB-1234', 'DL01AB1234' all become 'DL01AB1234'.
    """
    return "".join(ch for ch in value.upper() if ch.isalnum())


async def match_watchlist(db: AsyncSession, raw_vehicle_number: str) -> Watchlist | None:
    """Return the active watchlist entry for this plate, or None."""
    normalised = normalize_vehicle_number(raw_vehicle_number)
    result = await db.execute(
        select(Watchlist).filter(Watchlist.identifier == normalised, Watchlist.active.is_(True))
    )
    return result.scalar_one_or_none()
