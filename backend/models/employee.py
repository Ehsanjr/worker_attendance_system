from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    national_id = Column(String, nullable=True, unique=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    allowed_days = Column(String, default="0,1,2,3,4,5,6") # 0=دوشنبه تا 6=یکشنبه
    shift_start = Column(String, default="00:00")
    shift_end = Column(String, default="23:59")

    face_embeddings = relationship(
        "FaceEmbedding",
        back_populates="employee",
        cascade="all, delete"
    )

    attendance_events = relationship(
        "AttendanceEvent",
        back_populates="employee"
    )
