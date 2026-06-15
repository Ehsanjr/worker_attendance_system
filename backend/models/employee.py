from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
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
    is_deleted = Column(Boolean, default=False)
    
    # ستون‌های قدیمی را نگه می‌داریم تا دیتابیس کرش نکند، اما دیگر از آن‌ها استفاده نمی‌کنیم
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    allowed_days = Column(String, default="0,1,2,3,4,5,6")
    shift_start = Column(String, default="00:00")
    shift_end = Column(String, default="23:59")

    face_embeddings = relationship("FaceEmbedding", back_populates="employee", cascade="all, delete")
    attendance_events = relationship("AttendanceEvent", back_populates="employee")
    
    # --- ارتباط جدید با جدول شیفت‌ها ---
    shifts = relationship("EmployeeShift", back_populates="employee", cascade="all, delete")

class EmployeeShift(Base):
    __tablename__ = "employee_shifts"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    allowed_days = Column(String, default="0,1,2,3,4,5,6")
    shift_start = Column(String, default="00:00")
    shift_end = Column(String, default="23:59")
    is_deleted = Column(Boolean, default=False)

    employee = relationship("Employee", back_populates="shifts")