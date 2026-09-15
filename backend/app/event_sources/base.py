"""
event_sources/base.py

Abstract interface for camera event sources.
This is the architectural boundary between the application domain and any real
camera/VMS/ANPR integration.

PoC implementation: MockEventSource
Future implementation: FutureRTSPEventSource, ONVIFEventSource, etc.

A real adapter only needs to:
  1. Subclass EventSource
  2. Implement start() to emit EventCreate payloads
  3. Call self._on_event(payload) for each detection
  4. Swap it in via dependency injection or config
"""
from abc import ABC, abstractmethod
from typing import Callable
from app.schemas.event import EventCreate


class EventSource(ABC):
    """Base class for all camera event sources (mock or real)."""

    def __init__(self, on_event: Callable[[EventCreate], None]):
        """
        Args:
            on_event: Callback invoked for each new detection event.
                      In the PoC this calls process_event(); in production
                      it might publish to a message bus.
        """
        self._on_event = on_event

    @abstractmethod
    def start(self) -> None:
        """Begin emitting events. May be blocking or spawn a background thread."""
        raise NotImplementedError

    def stop(self) -> None:
        """Gracefully stop the event source. Override if needed."""
        pass
