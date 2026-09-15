"""
event_sources/mock_source.py

MockEventSource — emits the 12 representative ANPR events from spec §11.
Implements the EventSource interface so it can be dropped in/out without
changing the rest of the application.

Usage (in seed.py or a background task):
    source = MockEventSource(on_event=lambda p: process_event(db, p))
    source.start()   # calls on_event once per demo event

FutureRTSPEventSource:
    class FutureRTSPEventSource(EventSource):
        # real implementation later — connects to RTSP/ONVIF/Vendor API
        # and calls self._on_event(normalized_event) for each ANPR result
        def start(self): raise NotImplementedError
"""
import time
from datetime import datetime, timezone
from typing import Callable

from app.schemas.event import EventCreate
from app.event_sources.base import EventSource

# Demo events from spec §11 — vehicle DL01AB1234 crossing 12 cameras
DEMO_EVENTS = [
    {"camera_id": "Camera-01",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T09:58:00Z", "latitude": 28.6139, "longitude": 77.2090, "confidence": 0.98},
    {"camera_id": "Camera-02",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:00:30Z", "latitude": 28.6155, "longitude": 77.2100, "confidence": 0.97},
    {"camera_id": "Camera-03",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:01:45Z", "latitude": 28.6170, "longitude": 77.2110, "confidence": 0.95},
    {"camera_id": "Camera-04",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:02:30Z", "latitude": 28.6180, "longitude": 77.2120, "confidence": 0.96},
    {"camera_id": "Camera-05",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:03:15Z", "latitude": 28.6185, "longitude": 77.2130, "confidence": 0.94},
    {"camera_id": "Camera-06",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:04:00Z", "latitude": 28.6190, "longitude": 77.2140, "confidence": 0.97},
    {"camera_id": "Camera-07",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:04:32Z", "latitude": 28.6200, "longitude": 77.2150, "confidence": 0.96},
    {"camera_id": "Camera-08",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:05:45Z", "latitude": 28.6210, "longitude": 77.2160, "confidence": 0.95},
    {"camera_id": "Camera-09",  "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:06:30Z", "latitude": 28.6220, "longitude": 77.2170, "confidence": 0.98},
    {"camera_id": "Camera-10", "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:07:15Z", "latitude": 28.6230, "longitude": 77.2180, "confidence": 0.94},
    {"camera_id": "Camera-11", "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:08:00Z", "latitude": 28.6240, "longitude": 77.2190, "confidence": 0.96},
    {"camera_id": "Camera-12", "vehicle_number": "DL01AB1234", "event_time": "2026-09-15T10:09:30Z", "latitude": 28.6250, "longitude": 77.2200, "confidence": 0.97},
]


class MockEventSource(EventSource):
    """
    Simulates ANPR detections for the demo vehicle.
    Implements the same EventSource interface a real RTSP adapter would use.
    """

    def __init__(self, on_event: Callable[[EventCreate], None], delay: float = 0.0):
        super().__init__(on_event)
        self._delay = delay  # seconds between events; 0 for instant (seed mode)

    def start(self) -> None:
        """Emit all demo events, optionally with a delay between each."""
        for raw in DEMO_EVENTS:
            payload = EventCreate(
                camera_id=raw["camera_id"],
                vehicle_number=raw["vehicle_number"],
                event_time=datetime.fromisoformat(raw["event_time"].replace("Z", "+00:00")),
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                confidence=raw["confidence"],
                event_type="ANPR",
                attributes={"vehicle_type": "car"},
                source={"vendor": "SIMULATOR", "source_id": "SIM-001"}
            )
            self._on_event(payload)
            if self._delay > 0:
                time.sleep(self._delay)


# --- Placeholder for future real adapter ---
class FutureRTSPEventSource(EventSource):
    """
    Placeholder only — real implementation added when government feeds are available.
    Will connect to RTSP/ONVIF/Vendor API, run ANPR, and call self._on_event()
    with the same EventCreate schema, leaving all downstream logic unchanged.
    """

    def start(self) -> None:
        raise NotImplementedError(
            "FutureRTSPEventSource is a placeholder. "
            "Implement RTSP/ONVIF connection and ANPR inference here."
        )
