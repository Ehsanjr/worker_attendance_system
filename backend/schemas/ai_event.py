from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AIEvent(BaseModel):
    employee_id: int
    event: str
    track_id: Optional[int] = None
    confidence: Optional[float] = None
    camera_id: int
    time: datetime
