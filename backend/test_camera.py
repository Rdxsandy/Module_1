"""test_camera.py — temporary manual test for RTSPEventSource -> Colab AI connection."""
from app.event_sources.rtsp_source import RTSPEventSource
from app.schemas.event import EventCreate


def my_test_callback(payload: EventCreate):
    print("\nSUCCESS! Your local app received this payload ready for RabbitMQ:")
    print(payload.model_dump_json(indent=2))
    print("\n")


if __name__ == "__main__":
    source = RTSPEventSource(on_event=my_test_callback)
    source.start()
