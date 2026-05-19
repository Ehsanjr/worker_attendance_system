from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(Integer, ForeignKey("employees.id"))

    camera_id = Column(Integer, ForeignKey("cameras.id"))

    event_type = Column(String, nullable=False)

    confidence = Column(Float, nullable=True)

    track_id = Column(Integer, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    employee = relationship(
        "Employee",
        back_populates="attendance_events"
    )

    camera = relationship(
        "Camera",
        back_populates="attendance_events"
    )
