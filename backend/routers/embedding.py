from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.employee import Employee

router = APIRouter(
    prefix="/embeddings",
    tags=["AI"]
)

@router.get("/")
def get_all_embeddings(db: Session = Depends(get_db)):
    result = []

    employees = db.query(Employee).all()

    for emp in employees:
        for fe in emp.face_embeddings:
            result.append({
                "employee_id": emp.id,
                "name": emp.name,
                "embedding": fe.embedding
            })

    return result
