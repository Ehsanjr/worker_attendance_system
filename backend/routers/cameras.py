from fastapi import APIRouter, HTTPException
from typing import List

from schemas.camera import CameraCreate, CameraResponse

router = APIRouter(prefix="/cameras", tags=["cameras"])

fake_db = []
id_counter = 1


@router.post("/", response_model=CameraResponse)
def create_camera(camera: CameraCreate):

    global id_counter

    cam = {
        "id": id_counter,
        "name": camera.name,
        "rtsp_url": camera.rtsp_url,
        "location": camera.location,
        "is_active": camera.is_active,
        "created_at": "2026-01-01T00:00:00"
    }

    fake_db.append(cam)
    id_counter += 1

    return cam


@router.get("/", response_model=List[CameraResponse])
def list_cameras():
    return fake_db


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: int):

    for cam in fake_db:
        if cam["id"] == camera_id:
            return cam

    raise HTTPException(status_code=404, detail="Camera not found")


@router.delete("/{camera_id}")
def delete_camera(camera_id: int):

    for cam in fake_db:
        if cam["id"] == camera_id:
            fake_db.remove(cam)
            return {"message": "camera deleted"}

    raise HTTPException(status_code=404, detail="Camera not found")
