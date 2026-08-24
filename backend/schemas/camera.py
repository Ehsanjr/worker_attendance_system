from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class CameraBase(BaseModel):
    name: str
    type: str
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True