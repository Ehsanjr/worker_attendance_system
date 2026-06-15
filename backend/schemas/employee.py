from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# -------- Shifts Schemas --------
class EmployeeShiftBase(BaseModel):
    camera_id: Optional[int] = None
    allowed_days: Optional[str] = "0,1,2,3,4,5,6"
    shift_start: Optional[str] = "00:00"
    shift_end: Optional[str] = "23:59"

class EmployeeShiftCreate(EmployeeShiftBase):
    pass

class EmployeeShiftResponse(EmployeeShiftBase):
    id: int
    employee_id: int
    is_deleted: bool

    class Config:
        from_attributes = True

# -------- Employee Schemas --------
class EmployeeBase(BaseModel):
    name: str
    national_id: Optional[str] = None
    phone_number: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    # هنگام ثبت‌نام، می‌توانیم آرایه‌ای از شیفت‌ها را مستقیم بفرستیم
    shifts: Optional[List[EmployeeShiftCreate]] = []

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    national_id: Optional[str] = None
    phone_number: Optional[str] = None

class FaceEmbeddingResponse(BaseModel):
    id: int
    image_path: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class EmployeeResponse(EmployeeBase):
    id: int
    created_at: datetime
    is_deleted: bool
    shifts: List[EmployeeShiftResponse] = [] # 🔴 اضافه شدن لیست شیفت‌ها به خروجی

    class Config:
        from_attributes = True

class FaceEmbeddingCreate(BaseModel):
    embedding: list
    image_path: str