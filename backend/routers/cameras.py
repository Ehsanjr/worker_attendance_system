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
        rtsp_url=camera.rtsp_url,
        location=camera.location,
        is_active=camera.is_active
    )

    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)

    return db_camera


@router.get("/", response_model=List[CameraResponse])
def list_cameras(db: Session = Depends(get_db)):

    cameras = db.query(Camera).all()
    return cameras


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: int, db: Session = Depends(get_db)):

    camera = db.query(Camera).filter(Camera.id == camera_id).first()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    return camera


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):

    camera = db.query(Camera).filter(Camera.id == camera_id).first()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    db.delete(camera)
    db.commit()

    return {"message": "camera deleted"}
