from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.employee import Employee
from models.face_embedding import FaceEmbedding
from schemas.employee import FaceEmbeddingCreate
from schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
)

router = APIRouter(prefix="/employees", tags=["employees"])

@router.post("/", response_model=EmployeeResponse)
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    db_employee = Employee(
        name=employee.name,
        national_id=employee.national_id,
        phone_number=employee.phone_number
    )
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.get("/", response_model=List[EmployeeResponse])
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).all()

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return db_employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.name is not None:
        db_employee.name = data.name
    if data.national_id is not None:
        db_employee.national_id = data.national_id
    if data.phone_number is not None:
        db_employee.phone_number = data.phone_number

    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.delete("/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    db.delete(db_employee)
    db.commit()
    return {"status": "deleted", "employee_id": employee_id}


@router.post("/{employee_id}/embeddings")
def add_face_embedding(employee_id: int, data: FaceEmbeddingCreate, db: Session = Depends(get_db)):
    db_embedding = FaceEmbedding(
        employee_id=employee_id,
        embedding=data.embedding,
        image_path=data.image_path
    )
    db.add(db_embedding)
    db.commit()
    db.refresh(db_embedding)
    return {"status": "success", "embedding_id": db_embedding.id}