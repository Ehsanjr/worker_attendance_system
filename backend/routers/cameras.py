from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

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
