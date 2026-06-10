from sqlalchemy import Column, Integer, String, DateTime
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

    face_embeddings = relationship(
        "FaceEmbedding",
        back_populates="employee",
        cascade="all, delete"
    )

    attendance_events = relationship(
        "AttendanceEvent",
        back_populates="employee"
    )
