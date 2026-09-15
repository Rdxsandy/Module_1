from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
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
def get_dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera_count = db.query(Camera).count()
    online_count = db.query(Camera).filter(Camera.status == "ONLINE").count()
    offline_count = db.query(Camera).filter(Camera.status == "OFFLINE").count()
    maintenance_count = db.query(Camera).filter(Camera.status == "MAINTENANCE").count()
    
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    events_today = db.query(VehicleEvent).filter(VehicleEvent.event_time >= today).count()
    
    new_alerts = db.query(Alert).filter(Alert.status == "NEW").count()
    watchlist_count = db.query(Watchlist).count()
    
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
def get_recent_alerts(
    limit: int = 5,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
    from app.schemas.alert import AlertOut
    return [AlertOut.model_validate(a) for a in alerts]
