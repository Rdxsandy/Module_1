"""
event_sources/traffic_simulator.py

LiveTrafficSimulator — generates randomized ANPR events for MULTIPLE vehicles
across the registered camera network, continuously, until stopped.

This is distinct from MockEventSource (mock_source.py), which replays a fixed
12-event single-vehicle route used only for deterministic demo seeding
(see seed/demo_seed.py). The "Start Simulator" control on the dashboard uses
this class instead, so operators see realistic multi-vehicle live traffic
rather than one plate looping through the same route.
"""
import random
import string
import threading
from datetime import datetime, timezone
from typing import Callable, List, TypedDict

from app.schemas.event import EventCreate
from app.event_sources.base import EventSource

STATE_CODES = ["DL", "HR", "UP", "MH", "KA", "RJ", "PB", "GJ"]
VEHICLE_TYPES = ["car", "bike", "truck", "bus", "auto"]


class CameraInfo(TypedDict):
    name: str
    latitude: float
    longitude: float


def random_plate() -> str:
    """Generate a plausible Indian-style plate, e.g. 'HR26CJ4291'."""
    state = random.choice(STATE_CODES)
    rto = random.randint(1, 99)
    letters = "".join(random.choices(string.ascii_uppercase, k=2))
    digits = random.randint(1000, 9999)
    return f"{state}{rto:02d}{letters}{digits}"


class LiveTrafficSimulator(EventSource):
    """
    Emits one randomized event every `interval` seconds, alternating between
    a pool of vehicles (watchlisted plates + freshly generated ones) and the
    given cameras, until stop() is called.
    """

    def __init__(
        self,
        on_event: Callable[[EventCreate], None],
        cameras: List[CameraInfo],
        watchlist_plates: List[str] | None = None,
        interval: float = 2.0,
        extra_vehicle_count: int = 9,
    ):
        super().__init__(on_event)
        self._cameras = cameras
        self._interval = interval
        self._stop_event = threading.Event()
        self.plates: List[str] = list(dict.fromkeys(watchlist_plates or [])) + [
            random_plate() for _ in range(extra_vehicle_count)
        ]

    def stop(self) -> None:
        self._stop_event.set()

    def start(self) -> None:
        if not self._cameras:
            return
        while not self._stop_event.is_set():
            camera = random.choice(self._cameras)
            plate = random.choice(self.plates)
            payload = EventCreate(
                camera_id=camera["name"],
                vehicle_number=plate,
                event_time=datetime.now(timezone.utc),
                latitude=camera["latitude"] + random.uniform(-0.0015, 0.0015),
                longitude=camera["longitude"] + random.uniform(-0.0015, 0.0015),
                confidence=round(random.uniform(0.85, 0.99), 2),
                event_type="ANPR",
                attributes={"vehicle_type": random.choice(VEHICLE_TYPES)},
                source={"vendor": "SIMULATOR", "source_id": "SIM-LIVE"},
            )
            self._on_event(payload)
            self._stop_event.wait(self._interval)
