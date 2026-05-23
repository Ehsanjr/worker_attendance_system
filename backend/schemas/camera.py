from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from sqlalchemy import JSON


class CameraBase(BaseModel):
    name: str
    type: str
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    zones: Optional[List[int]] = None 
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
