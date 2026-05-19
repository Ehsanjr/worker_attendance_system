from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.ai_event import AIEvent
from models.attendance_event import AttendanceEvent

router = APIRouter(prefix="/ai-events", tags=["ai-events"])


@router.post("/")
def receive_ai_event(event: AIEvent, db: Session = Depends(get_db)):

    db_event = AttendanceEvent(
        employee_id=event.employee_id,
        camera_id=event.camera_id,
        event_type=event.event,
        confidence=event.confidence,
        track_id=event.track_id,
        timestamp=event.time
    )

    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return {"status": "stored", "event_id": db_event.id}

@router.get("/")
def list_ai_events(db: Session = Depends(get_db)):
    events = db.query(AttendanceEvent).all()
    return events