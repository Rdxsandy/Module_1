# backend/app/models/__init__.py
from .camera import Camera
from .watchlist import Watchlist
from .vehicle_event import VehicleEvent
from .alert import Alert
from .user import User
from .audit_log import AuditLog

__all__ = ["Camera", "Watchlist", "VehicleEvent", "Alert", "User", "AuditLog"]
