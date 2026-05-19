from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


# -------- Base --------

class EmployeeBase(BaseModel):
    name: str


# -------- Create --------

class EmployeeCreate(EmployeeBase):
    """
    برای ساخت کارگر جدید
    """
    pass


# -------- Update --------

class EmployeeUpdate(BaseModel):
    """
    برای ویرایش اطلاعات کارگر
    """
    name: Optional[str] = None


# -------- Face Embedding Schema --------

class FaceEmbeddingResponse(BaseModel):
    id: int
    embedding: List[float]
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
