# backend/app/schemas/__init__.py
from .camera import CameraCreate, CameraOut
from .event import EventCreate, EventOut
from .watchlist import WatchlistCreate, WatchlistOut
from .alert import AlertOut

__all__ = ["CameraCreate", "CameraOut", "EventCreate", "EventOut",
           "WatchlistCreate", "WatchlistOut", "AlertOut"]
