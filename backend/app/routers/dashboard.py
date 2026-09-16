from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.camera import Camera
from app.models.vehicle_event import VehicleEvent
from app.models.watchlist import Watchlist
from app.models.alert import Alert

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera_count = (await db.execute(select(func.count(Camera.id)))).scalar_one()
    online_count = (await db.execute(select(func.count(Camera.id)).filter(Camera.status == "ONLINE"))).scalar_one()
    offline_count = (await db.execute(select(func.count(Camera.id)).filter(Camera.status == "OFFLINE"))).scalar_one()
    maintenance_count = (await db.execute(select(func.count(Camera.id)).filter(Camera.status == "MAINTENANCE"))).scalar_one()

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    events_today = (await db.execute(
        select(func.count(VehicleEvent.id)).filter(VehicleEvent.event_time >= today)
    )).scalar_one()

    new_alerts = (await db.execute(select(func.count(Alert.id)).filter(Alert.status == "NEW"))).scalar_one()
    watchlist_count = (await db.execute(select(func.count(Watchlist.id)))).scalar_one()

    return {
        "camera_count": camera_count,
        "online_count": online_count,
        "offline_count": offline_count,
        "maintenance_count": maintenance_count,
        "events_today": events_today,
        "new_alerts": new_alerts,
        "watchlist_count": watchlist_count
    }

@router.get("/recent-alerts")
async def get_recent_alerts(
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Alert).order_by(Alert.created_at.desc()).limit(limit))
    alerts = result.scalars().all()
    from app.schemas.alert import AlertOut
    return [AlertOut.model_validate(a) for a in alerts]
