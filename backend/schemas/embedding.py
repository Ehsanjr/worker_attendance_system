from pydantic import BaseModel
from typing import List

class FaceEmbeddingOut(BaseModel):
    employee_id: int
    name: str
    embedding: List[float]

    class Config:
        orm_mode = True
