from sqlalchemy import Column, Integer, ForeignKey, JSON, DateTime, String
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(Integer, ForeignKey("employees.id"))

    embedding = Column(JSON, nullable=False)

    image_path = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship(
        "Employee",
        back_populates="face_embeddings"
    )
