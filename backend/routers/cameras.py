from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.camera import Camera
from schemas.camera import CameraCreate, CameraResponse

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.post("/", response_model=CameraResponse)
def create_camera(camera: CameraCreate, db: Session = Depends(get_db)):

    db_camera = Camera(
        name=camera.name,
        type=camera.type,
        rtsp_url=camera.rtsp_url,
        location=camera.location,
        zones=camera.zones,
        is_active=camera.is_active
    )

    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)

    return db_camera


@router.get("/")
def list_cameras(db: Session = Depends(get_db)):
    # فقط دوربین‌هایی که حذف نشده‌اند
    return db.query(Camera).filter(Camera.is_deleted == False).all()


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    db_camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not db_camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # 🔴 حذف نرم دوربین
    db_camera.is_deleted = True
    db.commit()
    return {"status": "soft_deleted", "camera_id": camera_id}




# ساختار دیتای دریافتی از فرانت‌اند برای ویرایش دوربین
class CameraUpdatePayload(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    zones: Optional[list] = None
    is_active: Optional[bool] = None

# مسیر (Route) جدید برای متد PUT جهت ویرایش
@router.put("/{camera_id}")
def update_camera(camera_id: int, payload: CameraUpdatePayload, db: Session = Depends(get_db)):
    # پیدا کردن دوربین از دیتابیس
    db_camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not db_camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # اعمال تغییرات جدید روی دیتابیس
    if payload.name is not None: db_camera.name = payload.name
    if payload.type is not None: db_camera.type = payload.type
    if payload.rtsp_url is not None: db_camera.rtsp_url = payload.rtsp_url
    if payload.location is not None: db_camera.location = payload.location
    if payload.zones is not None: db_camera.zones = payload.zones
    if payload.is_active is not None: db_camera.is_active = payload.is_active

    db.commit()
    db.refresh(db_camera)
    return db_camera