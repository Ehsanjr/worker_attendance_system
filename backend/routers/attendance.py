from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.attendance_event import AttendanceEvent
from schemas.attendance_event import AttendanceEventResponse

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/", response_model=List[AttendanceEventResponse])
def list_attendance_events(db: Session = Depends(get_db)):
    events = db.query(AttendanceEvent).all()
    return events


@router.get("/employee/{employee_id}", response_model=List[AttendanceEventResponse])
def get_employee_events(employee_id: int, db: Session = Depends(get_db)):
    events = (
        db.query(AttendanceEvent)
        .filter(AttendanceEvent.employee_id == employee_id)
        .all()
    )
    return events
