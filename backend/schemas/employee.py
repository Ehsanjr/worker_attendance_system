from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# -------- Base --------
class EmployeeBase(BaseModel):
    name: str
    national_id: Optional[str] = None
    phone_number: Optional[str] = None
    camera_id: Optional[int] = None
    allowed_days: Optional[str] = "0,1,2,3,4,5,6"
    shift_start: Optional[str] = "00:00"
    shift_end: Optional[str] = "23:59"

# -------- Create --------
class EmployeeCreate(EmployeeBase):
    pass

# -------- Update --------
class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    national_id: Optional[str] = None
    phone_number: Optional[str] = None
    camera_id: Optional[int] = None
    allowed_days: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None

# -------- Face Embedding Schema --------
class FaceEmbeddingResponse(BaseModel):
    id: int
    image_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# -------- Response --------
class EmployeeResponse(EmployeeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# -------- Employee + Embeddings --------
class EmployeeWithEmbeddings(EmployeeResponse):
    face_embeddings: List[FaceEmbeddingResponse] = []

    class Config:
        from_attributes = True

class FaceEmbeddingCreate(BaseModel):
    embedding: list
    image_path: str