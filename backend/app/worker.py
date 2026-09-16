"""
worker.py — Celery application for async vehicle event processing.

Decouples POST /api/events from the DB write + watchlist match: the API
just queues the payload here, and this worker performs the actual
validation, persistence, and alerting.

Run as a separate process:
    celery -A app.worker.celery_app worker --loglevel=info
"""
import asyncio
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


# One persistent event loop per worker process (not asyncio.run() per task):
# asyncpg connections are bound to the loop that created them, so a fresh
# loop per task would strand the async engine's pooled connections and
# force a brand-new (SSL) handshake with Neon on every single event.
# Created lazily so a prefork worker's forked children each get their own
# loop instead of inheriting the parent's (asyncio loops aren't fork-safe).
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop


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

    Celery invokes tasks synchronously, so this bridges into the async DB
    session via this worker process's persistent event loop.
    """
    _get_worker_loop().run_until_complete(_process_vehicle_event(payload_json))


async def _process_vehicle_event(payload_json: str) -> None:
    from app.database import SessionLocal
    from app.schemas.event import EventCreate
    from app.services.event_service import process_event

    payload = EventCreate.model_validate_json(payload_json)
    async with SessionLocal() as db:
        try:
            event, alert = await process_event(db, payload)
            alert_info = f" -> ALERT #{alert.id}" if alert else ""
            logger.info(f"Processed event #{event.id} ({payload.vehicle_number}){alert_info}")
        except ValueError as exc:
            logger.warning(f"Dropping event for camera '{payload.camera_id}': {exc}")
        except OperationalError:
            await db.rollback()
            raise
