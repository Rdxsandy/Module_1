"""
event_sources/rtsp_source.py

RTSPEventSource — connects to a real video feed (webcam, video file, or RTSP
URL), extracts frames, and sends them to the Google Colab ANPR service for
inference. Implements the same EventSource interface as MockEventSource /
LiveTrafficSimulator so it can be dropped in without changing any downstream
processing logic.

video_source accepts anything cv2.VideoCapture understands:
  - 0 (int)                        -> default webcam
  - "path/to/video.mp4"             -> uploaded video file (dashboard button)
  - "rtsp://user:pass@host/stream"  -> a real IP camera feed
"""
import os
import threading
import cv2
import requests
from datetime import datetime, timezone
from typing import Callable, Union
from dotenv import load_dotenv

from app.schemas.event import EventCreate
from app.event_sources.base import EventSource

# Loaded here too (not just in app.database) so this module also works when
# run standalone via test_camera.py, without importing the rest of the app.
load_dotenv()


class RTSPEventSource(EventSource):
    """
    Connects to a real video feed (webcam, file, or RTSP URL),
    and sends frames to the Google Colab AI service for processing.
    """

    def __init__(
        self,
        on_event: Callable[[EventCreate], None],
        camera_id: str = "Camera-01",
        video_source: Union[str, int] = 0,
        colab_url: str | None = None,
        latitude: float = 28.6139,
        longitude: float = 77.2090,
        frame_interval: float | None = None,
        on_frame: Callable[[bytes | None, dict], None] | None = None,
        min_confidence: float | None = None,
    ):
        super().__init__(on_event)
        self.camera_id = camera_id
        self.video_source = video_source
        self.colab_url = colab_url or os.getenv("COLAB_ANPR_URL")
        if not self.colab_url:
            raise ValueError(
                "COLAB_ANPR_URL is not set. Add it to backend/.env, "
                "e.g. COLAB_ANPR_URL=https://<your-ngrok-subdomain>.ngrok-free.dev/predict"
            )
        # Plates below this confidence are skipped instead of becoming events —
        # kept near 0 for now since the current ANPR model's confidence scores
        # run very low (1-6%) even on real reads; raise this once the model
        # improves. Override via ANPR_MIN_CONFIDENCE in backend/.env.
        self.min_confidence = (
            min_confidence if min_confidence is not None
            else float(os.getenv("ANPR_MIN_CONFIDENCE", "0.0"))
        )
        # Wait between captures, mainly there to avoid spamming the Colab API.
        # Kept short by default since it directly multiplies total processing
        # time (every frame waits this long before the next capture, on top
        # of the request round-trip). Override via ANPR_FRAME_INTERVAL.
        self.frame_interval = (
            frame_interval if frame_interval is not None
            else float(os.getenv("ANPR_FRAME_INTERVAL", "1.0"))
        )

        # Hardcoded GPS coordinates for the demo — override per-camera as needed.
        self.latitude = latitude
        self.longitude = longitude
        self._stop_event = threading.Event()
        # Optional observer invoked after every processed frame (not just
        # detections) so callers can confirm the feed is actually flowing —
        # e.g. to drive a live status page. Never required by the pipeline.
        self.on_frame = on_frame

    def stop(self) -> None:
        self._stop_event.set()

    def start(self) -> None:
        print(f"Starting video feed for {self.camera_id} from {self.video_source!r}...")

        # Force the FFMPEG backend explicitly. The default (MSMF on Windows)
        # can report isOpened()=True for a file with no video track and then
        # hang forever on read() instead of failing — FFMPEG fails fast and
        # cleanly instead, so source_error actually fires.
        cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG)

        if not cap.isOpened():
            print(f"Error: Could not open video source {self.video_source!r}.")
            if self.on_frame:
                self.on_frame(None, {"status": "source_error", "message": f"Could not open video source {self.video_source!r}"})
            return

        try:
            while not self._stop_event.is_set():
                # 1. Read a frame from the feed
                ret, frame = cap.read()
                if not ret:
                    print("End of video feed reached.")
                    if self.on_frame:
                        self.on_frame(None, {"status": "ended"})
                    break

                print("Captured frame, sending to Colab AI...")

                # 2. Convert the image frame to bytes
                _, img_encoded = cv2.imencode('.jpg', frame)
                image_bytes = img_encoded.tobytes()

                # 3. Send the image to the Colab Ngrok URL
                try:
                    files = {'file': ('frame.jpg', image_bytes, 'image/jpeg')}
                    response = requests.post(self.colab_url, files=files, timeout=15)

                    if response.status_code == 200:
                        result = response.json()
                        plate = result.get("plate")
                        confidence = result.get("confidence", 0.0)

                        # 4. If Colab found a plate above the confidence floor, create the Event payload!
                        if plate and confidence < self.min_confidence:
                            print(f"Plate '{plate}' below confidence threshold ({confidence:.2f} < {self.min_confidence}) — skipping")
                            if self.on_frame:
                                self.on_frame(image_bytes, {"status": "low_confidence", "plate": plate, "confidence": confidence})
                        elif plate:
                            print(f"DETECTED PLATE: {plate} (Conf: {confidence})")

                            payload = EventCreate(
                                camera_id=self.camera_id,
                                vehicle_number=plate,
                                event_time=datetime.now(timezone.utc),
                                latitude=self.latitude,
                                longitude=self.longitude,
                                confidence=confidence,
                                event_type="ANPR",
                                attributes={"vehicle_type": "car"},
                                source={"vendor": "COLAB_AI", "source_id": "RTSP-001"}
                            )
                            # 5. Send this event into the processing pipeline!
                            self._on_event(payload)
                            if self.on_frame:
                                self.on_frame(image_bytes, {"status": "detected", "plate": plate, "confidence": confidence})
                        else:
                            print("No plate found in this frame.")
                            if self.on_frame:
                                self.on_frame(image_bytes, {"status": "no_plate"})
                    else:
                        print(f"AI Server Error: {response.status_code}")
                        if self.on_frame:
                            self.on_frame(image_bytes, {"status": "ai_error", "message": f"HTTP {response.status_code}"})
                except requests.exceptions.RequestException as e:
                    print(f"Failed to connect to Colab: {e}")
                    if self.on_frame:
                        self.on_frame(image_bytes, {"status": "connection_error", "message": str(e)})

                # Wait between captures (interruptible by stop()) to avoid spamming the API
                self._stop_event.wait(self.frame_interval)

        finally:
            cap.release()
            print(f"Video feed for {self.camera_id} stopped.")
