from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AttendanceEventBase(BaseModel):
    employee_id: Optional[int] = None
    camera_id: Optional[int] = None
    event_type: str
    confidence: Optional[float] = None
    track_id: Optional[int] = None


class AttendanceEventResponse(AttendanceEventBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
