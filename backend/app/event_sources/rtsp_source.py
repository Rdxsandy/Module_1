"""
event_sources/rtsp_source.py

RTSPEventSource — connects to a real video feed (webcam, video file, or RTSP
URL), extracts frames, and runs ANPR locally (YOLOv8 vehicle detection +
EasyOCR plate reading) instead of round-tripping every frame to a remote
service. Implements the same EventSource interface as MockEventSource /
LiveTrafficSimulator so it can be dropped in without changing any downstream
processing logic.

video_source accepts anything cv2.VideoCapture understands:
  - 0 (int)                        -> default webcam
  - "path/to/video.mp4"             -> uploaded video file (dashboard button)
  - "rtsp://user:pass@host/stream"  -> a real IP camera feed

Architecture (3-thread pipeline — a slow DB or slow AI must never stall the
other two):
  Thread 1 — _read_frames (grabber): owns cv2.VideoCapture, does nothing but
    read frames as fast as the source allows and hand off the newest one via
    a maxsize=1 queue (older, un-consumed frames are simply overwritten —
    we always want the live edge, never a backlog). For a live source
    (RTSP/webcam) it reconnects with a fixed delay forever; for an uploaded
    file it ends the feed at EOF.
  Thread 2 — start() (AI worker, runs on the caller's thread): pulls the
    freshest frame, applies an optional ROI crop + background-subtraction
    motion filter to skip YOLO on frames with nothing new in them, runs
    YOLO + a lightweight IoU tracker so EasyOCR only runs a few times per
    vehicle (not once per frame it's in view), and hands detections off to
    the exporter instead of writing to the DB itself.
  Thread 3 — _export_worker (exporter): does the slow I/O — snapshot to
    disk, then the DB write via on_event — off the AI worker thread.
"""
import os
import threading
import queue
import time
import uuid
import cv2
import torch
import easyocr
from ultralytics import YOLO
from datetime import datetime, timezone
from typing import Callable, Union
from dotenv import load_dotenv

from app.schemas.event import EventCreate
from app.event_sources.base import EventSource

# Loaded here too (not just in app.database) so this module also works when
# run standalone via test_camera.py, without importing the rest of the app.
load_dotenv()

SNAPSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "snapshots"
)

# COCO class ids YOLOv8 was trained on: car, motorcycle, bus, truck.
VEHICLE_CLASSES = [2, 3, 5, 7]

# License plates are alphanumeric — restricting EasyOCR to this charset
# both speeds it up and cuts down on garbage reads from background text.
PLATE_ALLOWLIST = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Sentinels pushed through the frame queue to tell the AI worker the feed
# ended (file EOF) or never came up (bad source) — distinct from `None`,
# which is a perfectly normal (if unlikely) frame value.
_EOF_SENTINEL = object()
_ERROR_SENTINEL = object()


class VehicleTracker:
    """Minimal IoU-based multi-object tracker — no extra dependency (OpenCV's
    contrib trackers / ByteTrack aren't installed here). It only needs to
    answer one question per detection box: have we already read this
    vehicle's plate, and if not, is this frame worth spending an OCR call on?

    Heuristic: a vehicle crossing the frame gets bigger (closer/clearer)
    before it gets smaller (driving away) — so we only spend OCR attempts
    while a track's box is still growing, capped at max_attempts, and stop
    entirely once a read is confirmed.
    """

    def __init__(self, iou_threshold: float = 0.3, max_age: int = 15, max_attempts: int = 3):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.max_attempts = max_attempts
        self._tracks: dict[int, dict] = {}
        self._next_id = 1

    @staticmethod
    def _iou(a, b) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def update(self, boxes, frame_idx: int):
        """boxes: list of (x1,y1,x2,y2) in full-frame coords for this frame.
        Returns [(track_id, box, should_ocr), ...]."""
        results = []
        assigned = set()

        for box in boxes:
            best_id, best_iou = None, 0.0
            for tid, track in self._tracks.items():
                if tid in assigned:
                    continue
                iou = self._iou(box, track["box"])
                if iou > best_iou:
                    best_iou, best_id = iou, tid

            area = max(0, box[2] - box[0]) * max(0, box[3] - box[1])

            if best_id is not None and best_iou >= self.iou_threshold:
                track = self._tracks[best_id]
                track["box"] = box
                track["last_seen"] = frame_idx
                growing = area >= track["best_area"]
                if growing:
                    track["best_area"] = area
                should_ocr = growing and not track["confirmed"] and track["attempts"] < self.max_attempts
                if should_ocr:
                    track["attempts"] += 1
                assigned.add(best_id)
                results.append((best_id, box, should_ocr))
            else:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = {
                    "box": box, "last_seen": frame_idx, "best_area": area,
                    "attempts": 1, "confirmed": False,
                }
                assigned.add(tid)
                results.append((tid, box, True))

        stale = [tid for tid, t in self._tracks.items() if frame_idx - t["last_seen"] > self.max_age]
        for tid in stale:
            del self._tracks[tid]

        return results

    def confirm(self, track_id: int) -> None:
        """Plate successfully read — stop spending OCR attempts on this
        track for the rest of its time in frame."""
        if track_id in self._tracks:
            self._tracks[track_id]["confirmed"] = True


class RTSPEventSource(EventSource):
    """
    Connects to a real video feed (webcam, file, or RTSP URL) and runs
    YOLOv8 + EasyOCR locally to detect vehicles and read plates, using a
    3-thread producer/AI/exporter pipeline so slow AI inference or a slow
    database never stalls the video read.
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
        frame_skip: int | None = None,
    ):
        super().__init__(on_event)
        self.camera_id = camera_id
        self.video_source = video_source

        # --- Legacy Google Colab config — unused now that ANPR runs locally,
        # kept only so old callers passing colab_url/ANPR_FRAME_INTERVAL don't
        # break. See the commented-out Colab pipeline at the bottom of this
        # file for the previous HTTP-based implementation. ---
        self.colab_url = colab_url or os.getenv("COLAB_ANPR_URL")
        self.frame_interval = (
            frame_interval if frame_interval is not None
            else float(os.getenv("ANPR_FRAME_INTERVAL", "1.0"))
        )

        # OCR reads below this confidence are skipped instead of becoming
        # events. Override via ANPR_MIN_CONFIDENCE in backend/.env.
        self.min_confidence = (
            min_confidence if min_confidence is not None
            else float(os.getenv("ANPR_MIN_CONFIDENCE", "0.0"))
        )
        # Hard ceiling: run YOLO+OCR at least every Nth frame even with zero
        # motion (covers a stopped vehicle sitting in frame). The motion
        # filter below is what skips most frames in between.
        self.frame_skip = (
            frame_skip if frame_skip is not None
            else int(os.getenv("ANPR_FRAME_SKIP", "5"))
        )

        # ROI (Region of Interest), as fractions of frame width/height —
        # default is the full frame. Per-camera tuning (e.g. crop out sky
        # above the road) cuts YOLO's per-frame cost proportionally to the
        # cropped area. Override via ANPR_ROI_* in backend/.env.
        self.roi_x_start = float(os.getenv("ANPR_ROI_X_START", "0.0"))
        self.roi_y_start = float(os.getenv("ANPR_ROI_Y_START", "0.0"))
        self.roi_x_end = float(os.getenv("ANPR_ROI_X_END", "1.0"))
        self.roi_y_end = float(os.getenv("ANPR_ROI_Y_END", "1.0"))
        self._roi_box: tuple[int, int, int, int] | None = None  # computed lazily from frame size

        # Fraction of ROI pixels that must change (MOG2 background
        # subtraction) before a frame is worth running YOLO on at all.
        # Override via ANPR_MOTION_THRESHOLD.
        self.motion_threshold = float(os.getenv("ANPR_MOTION_THRESHOLD", "0.02"))
        self._bg_subtractor = None

        # Vehicle tracker config — avoids re-running EasyOCR on the same
        # vehicle every frame it's visible.
        self.track_iou_threshold = float(os.getenv("ANPR_TRACK_IOU_THRESHOLD", "0.3"))
        self.track_max_age = int(os.getenv("ANPR_TRACK_MAX_AGE", "15"))
        self.track_max_attempts = int(os.getenv("ANPR_TRACK_MAX_ATTEMPTS", "3"))
        self._tracker: VehicleTracker | None = None

        # EasyOCR struggles with tiny text — plate crops smaller than this
        # (in pixels, longest side) are upscaled before OCR.
        self.min_ocr_dim = int(os.getenv("ANPR_MIN_OCR_DIM", "200"))

        # Base delay before the first reconnect attempt for a live
        # (RTSP/webcam) source; doubles on each consecutive failure up to
        # reconnect_max_delay (exponential backoff — never tight-loops
        # against a camera that's actually down), and resets back to this
        # base once a connection delivers at least one real frame.
        # Uploaded video files never reconnect — EOF just ends the feed.
        self.reconnect_delay = float(os.getenv("ANPR_RECONNECT_DELAY", "2.0"))
        self.reconnect_max_delay = float(os.getenv("ANPR_RECONNECT_MAX_DELAY", "30.0"))
        # FFmpeg's default RTSP connect/read timeout can be very long (tens
        # of seconds, sometimes effectively unbounded over UDP to a dead
        # host) — without bounding it, a down camera hangs the grabber
        # thread well past what stop()/reconnect can react to.
        self.rtsp_connect_timeout = float(os.getenv("ANPR_RTSP_CONNECT_TIMEOUT", "5.0"))

        # Hardcoded GPS coordinates for the demo — override per-camera as needed.
        self.latitude = latitude
        self.longitude = longitude
        self._stop_event = threading.Event()
        # Optional observer invoked after every processed frame (not just
        # detections) so callers can confirm the feed is actually flowing —
        # e.g. to drive a live status page. Never required by the pipeline.
        self.on_frame = on_frame
        self._last_open_error: str | None = None

        # --- Local AI models, loaded once and reused for the life of the
        # feed (loading YOLO/EasyOCR per-frame would dominate latency). ---
        gpu_available = torch.cuda.is_available()
        # ONNX Runtime beats plain PyTorch for CPU inference; on a GPU box,
        # native PyTorch + CUDA is faster than onnxruntime's CPU-only build
        # here, so ONNX is only used when there's no GPU.
        self.use_onnx = (
            os.getenv("ANPR_USE_ONNX", "true").lower() in ("1", "true", "yes")
            and not gpu_available
        )
        self.yolo_model = self._load_yolo_model()
        self.ocr_reader = easyocr.Reader(["en"], gpu=gpu_available)

        # Thread 1 -> Thread 2 handoff: only the freshest frame is ever kept
        # (maxsize=1) — if the AI worker falls behind, older frames are
        # dropped rather than queued, so the feed always tracks live video.
        self.frame_queue: "queue.Queue" = queue.Queue(maxsize=1)
        # Thread 2 -> Thread 3 handoff: detected plates awaiting snapshot +
        # DB write. Bounded so a stuck DB can't grow this unboundedly; if it
        # fills, the oldest pending event is dropped rather than blocking
        # the AI worker.
        self.output_queue: "queue.Queue" = queue.Queue(maxsize=50)

    def stop(self) -> None:
        self._stop_event.set()

    def _load_yolo_model(self) -> YOLO:
        weights_path = "yolov8n.pt"
        if not self.use_onnx:
            return YOLO(weights_path)
        onnx_path = os.path.splitext(weights_path)[0] + ".onnx"
        try:
            if not os.path.exists(onnx_path):
                print("Exporting YOLOv8n to ONNX for faster CPU inference (one-time)...")
                YOLO(weights_path).export(format="onnx")
            return YOLO(onnx_path, task="detect")
        except Exception as e:
            print(f"ONNX export/load failed ({e}); falling back to PyTorch weights.")
            return YOLO(weights_path)

    # ------------------------------------------------------------------
    # Thread 1 — Frame Grabber: owns cv2.VideoCapture exclusively. Reads as
    # fast as the source allows; for a live source (RTSP/webcam) reconnects
    # forever on failure/drop, for an uploaded file it ends at EOF.
    # ------------------------------------------------------------------
    def _read_frames(self) -> None:
        is_live = not (isinstance(self.video_source, str) and os.path.isfile(self.video_source))
        is_rtsp = isinstance(self.video_source, str) and self.video_source.lower().startswith("rtsp://")

        if is_rtsp:
            # UDP (FFmpeg's default RTSP transport) frequently fails across
            # NAT/firewalls and silently produces corrupt frames instead of
            # a clean error — those then look like model bugs, not network
            # ones. Force TCP. This is a process-wide FFmpeg env var (see
            # the CAP_PROP_OPEN_TIMEOUT_MSEC comment below for the same
            # single-active-feed caveat).
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        current_delay = self.reconnect_delay
        while not self._stop_event.is_set():
            if is_rtsp:
                # OpenCV's own open/read timeout (CAP_PROP_OPEN_TIMEOUT_MSEC
                # / CAP_PROP_READ_TIMEOUT_MSEC) defaults to 30s and overrides
                # FFmpeg-level options like `stimeout` — without setting
                # these explicitly, a dead/unreachable camera hangs the
                # grabber thread for 30s per attempt regardless of
                # reconnect_delay. Passed as VideoCapture constructor params
                # (not cap.set(), which is too late for the open timeout).
                timeout_ms = int(self.rtsp_connect_timeout * 1000)
                cap = cv2.VideoCapture(
                    self.video_source, cv2.CAP_FFMPEG,
                    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms,
                     cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms],
                )
            else:
                # Force the FFMPEG backend explicitly. The default (MSMF on
                # Windows) can report isOpened()=True for a file with no
                # video track and then hang forever on read() instead of
                # failing — FFMPEG fails fast and cleanly instead.
                cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG)

            if not cap.isOpened():
                cap.release()
                message = f"Could not open video source {self.video_source!r}"
                print(f"Error: {message}.")
                if not is_live:
                    self._last_open_error = message
                    self._push_control(_ERROR_SENTINEL)
                    return
                if self.on_frame:
                    self.on_frame(None, {"status": "reconnecting", "message": f"{message} — retrying in {current_delay:.0f}s"})
                if self._stop_event.wait(current_delay):
                    return
                current_delay = min(current_delay * 2, self.reconnect_max_delay)
                continue

            frames_this_attempt = 0
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break
                frames_this_attempt += 1
                self._push_frame(frame)
                time.sleep(0.005)  # yield the GIL, avoid pinning a CPU core
            cap.release()

            if self._stop_event.is_set():
                return
            if not is_live:
                self._push_control(_EOF_SENTINEL)
                return

            # A connection that actually delivered frames means the camera
            # is healthy — reset backoff to the base delay rather than
            # keeping whatever it had climbed to from earlier failures.
            if frames_this_attempt > 0:
                current_delay = self.reconnect_delay

            print(f"Connection to {self.video_source!r} lost. Retrying in {current_delay:.0f}s...")
            if self.on_frame:
                self.on_frame(None, {"status": "reconnecting", "message": f"Connection lost, retrying in {current_delay:.0f}s"})
            if self._stop_event.wait(current_delay):
                return
            current_delay = min(current_delay * 2, self.reconnect_max_delay)

    def _push_frame(self, frame) -> None:
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
        self.frame_queue.put(frame)

    def _push_control(self, sentinel) -> None:
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
        self.frame_queue.put(sentinel)

    # ------------------------------------------------------------------
    # ROI cropping — computed once from the first frame's dimensions.
    # ------------------------------------------------------------------
    def _crop_roi(self, frame):
        if self._roi_box is None:
            h, w = frame.shape[:2]
            x1 = int(w * self.roi_x_start)
            y1 = int(h * self.roi_y_start)
            x2 = int(w * self.roi_x_end)
            y2 = int(h * self.roi_y_end)
            self._roi_box = (x1, y1, x2, y2)
        x1, y1, x2, y2 = self._roi_box
        return frame[y1:y2, x1:x2], (x1, y1)

    # ------------------------------------------------------------------
    # Local AI inference on a single frame: motion-gate, detect vehicles,
    # track them, and only OCR a tracked vehicle a few times total.
    # ------------------------------------------------------------------
    def _process_frame(self, frame, frame_count: int) -> None:
        roi_frame, (ox, oy) = self._crop_roi(frame)

        fg_mask = self._bg_subtractor.apply(roi_frame)
        motion_ratio = (cv2.countNonZero(fg_mask) / fg_mask.size) if fg_mask.size else 1.0
        should_scan = motion_ratio >= self.motion_threshold or frame_count % self.frame_skip == 0

        if not should_scan:
            if self.on_frame:
                _, img_encoded = cv2.imencode(".jpg", frame)
                self.on_frame(img_encoded.tobytes(), {"status": "streaming"})
            return

        _, img_encoded = cv2.imencode(".jpg", frame)
        frame_bytes = img_encoded.tobytes()

        # Step A: Detect vehicles (car, motorcycle, bus, truck) within the ROI.
        results = self.yolo_model(roi_frame, classes=VEHICLE_CLASSES, verbose=False)

        boxes = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                boxes.append((x1 + ox, y1 + oy, x2 + ox, y2 + oy))  # back to full-frame coords

        # Step B: Track vehicles across frames — only a handful of these
        # boxes come back with should_ocr=True per vehicle's time in frame.
        tracked = self._tracker.update(boxes, frame_count)

        plate_found = False
        any_candidate = False
        for track_id, (x1, y1, x2, y2), should_ocr in tracked:
            if not should_ocr:
                continue

            cropped = frame[max(y1, 0):y2, max(x1, 0):x2]
            if cropped.size == 0:
                continue

            # Enlarge small crops — EasyOCR struggles with tiny text.
            h, w = cropped.shape[:2]
            longest_side = max(h, w)
            if 0 < longest_side < self.min_ocr_dim:
                scale = self.min_ocr_dim / longest_side
                cropped = cv2.resize(cropped, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            # Step C: Read text off the cropped vehicle region, restricted
            # to plate-plausible characters.
            text_results = self.ocr_reader.readtext(cropped, allowlist=PLATE_ALLOWLIST, paragraph=False)

            for _, text, ocr_confidence in text_results:
                candidate = "".join(ch for ch in text if ch.isalnum()).upper()
                if len(candidate) <= 4:
                    continue
                any_candidate = True

                if ocr_confidence < self.min_confidence:
                    print(
                        f"Plate '{candidate}' below confidence threshold "
                        f"({ocr_confidence:.2f} < {self.min_confidence}) — skipping"
                    )
                    if self.on_frame:
                        self.on_frame(
                            frame_bytes,
                            {"status": "low_confidence", "plate": candidate, "confidence": ocr_confidence},
                        )
                    continue

                plate_found = True
                self._tracker.confirm(track_id)
                print(f"DETECTED PLATE: {candidate} (Conf: {ocr_confidence:.2f}, track {track_id})")

                # Step D (Thread 3 handoff): hand the slow work (snapshot +
                # DB write) to the exporter instead of doing it here.
                self._queue_export(frame_bytes, candidate, float(ocr_confidence))
                if self.on_frame:
                    self.on_frame(
                        frame_bytes,
                        {"status": "detected", "plate": candidate, "confidence": ocr_confidence},
                    )

        if not plate_found and not any_candidate and self.on_frame:
            self.on_frame(frame_bytes, {"status": "no_plate"})

    def _queue_export(self, frame_bytes: bytes, plate: str, confidence: float) -> None:
        item = {"frame_bytes": frame_bytes, "plate": plate, "confidence": confidence}
        try:
            self.output_queue.put_nowait(item)
        except queue.Full:
            # A backed-up exporter (DB/disk stalled) must not block the AI
            # worker — drop the oldest pending event rather than freeze the
            # live feed.
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                pass
            self.output_queue.put_nowait(item)

    def _save_snapshot(self, image_bytes: bytes, plate: str) -> str | None:
        """Local evidence snapshot (replaces an S3 upload) — a full disk
        must not crash the capture loop, just skip the snapshot."""
        try:
            os.makedirs(SNAPSHOT_DIR, exist_ok=True)
            filename = f"{uuid.uuid4().hex}_{plate}.jpg"
            with open(os.path.join(SNAPSHOT_DIR, filename), "wb") as f:
                f.write(image_bytes)
            return f"/api/static/snapshots/{filename}"
        except OSError as e:
            print(f"Failed to save snapshot for plate '{plate}': {e}")
            return None

    # ------------------------------------------------------------------
    # Thread 3 — Exporter: the slow work (disk snapshot + DB write via
    # on_event) happens here, off the AI worker thread, so a slow database
    # never stalls frame processing.
    # ------------------------------------------------------------------
    def _export_worker(self) -> None:
        while True:
            item = self.output_queue.get()
            if item is _EOF_SENTINEL:
                break
            try:
                snapshot_url = self._save_snapshot(item["frame_bytes"], item["plate"])
                payload = EventCreate(
                    camera_id=self.camera_id,
                    vehicle_number=item["plate"],
                    event_time=datetime.now(timezone.utc),
                    latitude=self.latitude,
                    longitude=self.longitude,
                    confidence=item["confidence"],
                    event_type="ANPR",
                    attributes={"vehicle_type": "car"},
                    source={"vendor": "LOCAL_YOLO_EASYOCR", "source_id": "RTSP-001"},
                    snapshot_url=snapshot_url,
                )
                self._on_event(payload)
            except Exception as e:
                print(f"Exporter failed for plate '{item.get('plate')}': {e}")

    # ------------------------------------------------------------------
    # Thread 2 — AI worker (runs on the caller's thread): pulls the
    # freshest frame and either runs full inference on it or streams it
    # straight through so the live preview stays smooth.
    # ------------------------------------------------------------------
    def start(self) -> None:
        print(f"Starting local AI video feed for {self.camera_id} from {self.video_source!r}...")

        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=False)
        self._tracker = VehicleTracker(
            iou_threshold=self.track_iou_threshold,
            max_age=self.track_max_age,
            max_attempts=self.track_max_attempts,
        )

        reader_thread = threading.Thread(target=self._read_frames, daemon=True)
        reader_thread.start()
        exporter_thread = threading.Thread(target=self._export_worker, daemon=True)
        exporter_thread.start()

        frame_count = 0
        try:
            while not self._stop_event.is_set():
                try:
                    item = self.frame_queue.get(timeout=0.5)
                except queue.Empty:
                    continue  # re-check _stop_event rather than block forever

                if item is _EOF_SENTINEL:
                    print("End of video feed reached.")
                    if self.on_frame:
                        self.on_frame(None, {"status": "ended"})
                    break

                if item is _ERROR_SENTINEL:
                    message = self._last_open_error or f"Could not open video source {self.video_source!r}"
                    if self.on_frame:
                        self.on_frame(None, {"status": "source_error", "message": message})
                    break

                frame_count += 1
                self._process_frame(item, frame_count)
        finally:
            self._stop_event.set()
            reader_thread.join(timeout=2)
            self.output_queue.put(_EOF_SENTINEL)
            exporter_thread.join(timeout=5)
            print(f"Video feed for {self.camera_id} stopped.")


# ======================================================================
# LEGACY: Google Colab HTTP-based ANPR pipeline — superseded by the local
# YOLOv8 + EasyOCR pipeline above. Kept commented out for reference/rollback
# rather than deleted.
# ======================================================================
#
# import requests
#
# class RTSPEventSource(EventSource):
#     def __init__(
#         self,
#         on_event: Callable[[EventCreate], None],
#         camera_id: str = "Camera-01",
#         video_source: Union[str, int] = 0,
#         colab_url: str | None = None,
#         latitude: float = 28.6139,
#         longitude: float = 77.2090,
#         frame_interval: float | None = None,
#         on_frame: Callable[[bytes | None, dict], None] | None = None,
#         min_confidence: float | None = None,
#     ):
#         super().__init__(on_event)
#         self.camera_id = camera_id
#         self.video_source = video_source
#         self.colab_url = colab_url or os.getenv("COLAB_ANPR_URL")
#         if not self.colab_url:
#             raise ValueError(
#                 "COLAB_ANPR_URL is not set. Add it to backend/.env, "
#                 "e.g. COLAB_ANPR_URL=https://<your-ngrok-subdomain>.ngrok-free.dev/predict"
#             )
#         self.min_confidence = (
#             min_confidence if min_confidence is not None
#             else float(os.getenv("ANPR_MIN_CONFIDENCE", "0.0"))
#         )
#         self.frame_interval = (
#             frame_interval if frame_interval is not None
#             else float(os.getenv("ANPR_FRAME_INTERVAL", "1.0"))
#         )
#         self.latitude = latitude
#         self.longitude = longitude
#         self._stop_event = threading.Event()
#         self.on_frame = on_frame
#
#     def stop(self) -> None:
#         self._stop_event.set()
#
#     def start(self) -> None:
#         print(f"Starting video feed for {self.camera_id} from {self.video_source!r}...")
#         cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG)
#         if not cap.isOpened():
#             print(f"Error: Could not open video source {self.video_source!r}.")
#             if self.on_frame:
#                 self.on_frame(None, {"status": "source_error", "message": f"Could not open video source {self.video_source!r}"})
#             return
#         try:
#             while not self._stop_event.is_set():
#                 ret, frame = cap.read()
#                 if not ret:
#                     print("End of video feed reached.")
#                     if self.on_frame:
#                         self.on_frame(None, {"status": "ended"})
#                     break
#
#                 print("Captured frame, sending to Colab AI...")
#                 _, img_encoded = cv2.imencode('.jpg', frame)
#                 image_bytes = img_encoded.tobytes()
#
#                 try:
#                     files = {'file': ('frame.jpg', image_bytes, 'image/jpeg')}
#                     response = requests.post(self.colab_url, files=files, timeout=15)
#
#                     if response.status_code == 200:
#                         result = response.json()
#                         plate = result.get("plate")
#                         confidence = result.get("confidence", 0.0)
#
#                         if plate and confidence < self.min_confidence:
#                             print(f"Plate '{plate}' below confidence threshold ({confidence:.2f} < {self.min_confidence}) — skipping")
#                             if self.on_frame:
#                                 self.on_frame(image_bytes, {"status": "low_confidence", "plate": plate, "confidence": confidence})
#                         elif plate:
#                             print(f"DETECTED PLATE: {plate} (Conf: {confidence})")
#
#                             snapshot_url = None
#                             try:
#                                 os.makedirs(SNAPSHOT_DIR, exist_ok=True)
#                                 filename = f"{uuid.uuid4().hex}_{plate}.jpg"
#                                 with open(os.path.join(SNAPSHOT_DIR, filename), "wb") as f:
#                                     f.write(image_bytes)
#                                 snapshot_url = f"/api/static/snapshots/{filename}"
#                             except OSError as e:
#                                 print(f"Failed to save snapshot for plate '{plate}': {e}")
#
#                             payload = EventCreate(
#                                 camera_id=self.camera_id,
#                                 vehicle_number=plate,
#                                 event_time=datetime.now(timezone.utc),
#                                 latitude=self.latitude,
#                                 longitude=self.longitude,
#                                 confidence=confidence,
#                                 event_type="ANPR",
#                                 attributes={"vehicle_type": "car"},
#                                 source={"vendor": "COLAB_AI", "source_id": "RTSP-001"},
#                                 snapshot_url=snapshot_url,
#                             )
#                             self._on_event(payload)
#                             if self.on_frame:
#                                 self.on_frame(image_bytes, {"status": "detected", "plate": plate, "confidence": confidence})
#                         else:
#                             print("No plate found in this frame.")
#                             if self.on_frame:
#                                 self.on_frame(image_bytes, {"status": "no_plate"})
#                     else:
#                         print(f"AI Server Error: {response.status_code}")
#                         if self.on_frame:
#                             self.on_frame(image_bytes, {"status": "ai_error", "message": f"HTTP {response.status_code}"})
#                 except requests.exceptions.RequestException as e:
#                     print(f"Failed to connect to Colab: {e}")
#                     if self.on_frame:
#                         self.on_frame(image_bytes, {"status": "connection_error", "message": str(e)})
#
#                 self._stop_event.wait(self.frame_interval)
#         finally:
#             cap.release()
#             print(f"Video feed for {self.camera_id} stopped.")
