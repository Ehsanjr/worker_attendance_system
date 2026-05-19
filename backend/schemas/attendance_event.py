from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AttendanceEventBase(BaseModel):
    employee_id: int
    camera_id: int
    event_type: str
    confidence: Optional[float] = None
    track_id: Optional[int] = None


class AttendanceEventResponse(AttendanceEventBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
