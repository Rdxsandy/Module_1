"""
worker.py — Celery application for async vehicle event processing.

Decouples POST /api/events from the DB write + watchlist match: the API
just queues the payload here, and this worker performs the actual
validation, persistence, and alerting.

Run as a separate process:
    celery -A app.worker.celery_app worker --loglevel=info
"""
import os
from dotenv import load_dotenv
load_dotenv()

from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.exc import OperationalError

logger = get_task_logger(__name__)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")

celery_app = Celery("cctv_worker", broker=CELERY_BROKER_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(
    name="process_vehicle_event_task",
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_vehicle_event_task(payload_json: str) -> None:
    """
    Validate + persist a queued vehicle event, matching the watchlist and
    raising an alert if needed.

    Invalid camera_id -> dropped and logged (not retried, not a transient
    failure). DB connectivity errors -> retried with backoff by Celery.
    """
    from app.database import SessionLocal
    from app.schemas.event import EventCreate
    from app.services.event_service import process_event

    payload = EventCreate.model_validate_json(payload_json)
    db = SessionLocal()
    try:
        event, alert = process_event(db, payload)
        alert_info = f" -> ALERT #{alert.id}" if alert else ""
        logger.info(f"Processed event #{event.id} ({payload.vehicle_number}){alert_info}")
    except ValueError as exc:
        logger.warning(f"Dropping event for camera '{payload.camera_id}': {exc}")
    except OperationalError:
        db.rollback()
        raise
    finally:
        db.close()
