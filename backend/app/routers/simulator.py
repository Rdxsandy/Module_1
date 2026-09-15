from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import threading

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User
from app.event_sources.mock_source import MockEventSource
from app.services.event_service import process_event
from app.schemas.event import EventCreate

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# Global state for simulator
simulator_thread = None
is_running = False

def run_simulator(db_session_factory, delay=2.0):
    global is_running
    is_running = True
    
    # We need a new db session for the thread
    db = next(db_session_factory())
    
    def on_event(payload: EventCreate):
        if not is_running:
            return
        try:
            process_event(db, payload)
        except Exception as e:
            print(f"Simulator error processing event: {e}")
            
    try:
        source = MockEventSource(on_event=on_event, delay=delay)
        source.start()
    finally:
        is_running = False
        db.close()

@router.post("/start")
def start_simulator(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    global simulator_thread, is_running
    if is_running:
        raise HTTPException(status_code=400, detail="Simulator is already running")
        
    def session_factory():
        from app.database import SessionLocal
        db_session = SessionLocal()
        try:
            yield db_session
        finally:
            db_session.close()
            
    simulator_thread = threading.Thread(target=run_simulator, args=(session_factory, 2.0))
    simulator_thread.start()
    return {"status": "started"}

@router.post("/stop")
def stop_simulator(
    user: User = Depends(require_admin),
):
    global is_running
    is_running = False
    return {"status": "stopped"}

@router.post("/emit")
def emit_single_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Manually emit a single event (like start but 1 event without thread)"""
    try:
        event, alert = process_event(db, payload)
        return {"status": "emitted", "event_id": event.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
def get_simulator_status(
    _: User = Depends(get_current_user),
):
    global is_running
    return {"running": is_running}
