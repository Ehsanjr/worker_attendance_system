from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    type = Column(String, nullable=False)

    rtsp_url = Column(String, nullable=True)

    location = Column(String, nullable=True)

    zones = Column(JSON, nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    attendance_events = relationship(
        "AttendanceEvent",
        back_populates="camera"
    )
