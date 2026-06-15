from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.employee import Employee, EmployeeShift
from models.face_embedding import FaceEmbedding
from schemas.employee import FaceEmbeddingCreate, EmployeeShiftCreate, EmployeeShiftResponse
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

    # ذخیره تمام شیفت‌هایی که از فرانت‌اند فرستاده شده
    for shift_data in employee.shifts:
        new_shift = EmployeeShift(
            employee_id=db_employee.id,
            camera_id=shift_data.camera_id,
            allowed_days=shift_data.allowed_days,
            shift_start=shift_data.shift_start,
            shift_end=shift_data.shift_end
        )
        db.add(new_shift)
    
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.get("/", response_model=List[EmployeeResponse])
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).filter(Employee.is_deleted == False).all()

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id, Employee.is_deleted == False).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return db_employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.name is not None: db_employee.name = data.name
    if data.national_id is not None: db_employee.national_id = data.national_id
    if data.phone_number is not None: db_employee.phone_number = data.phone_number

    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.delete("/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    db_employee.is_deleted = True 
    db.commit()
    return {"status": "soft_deleted", "employee_id": employee_id}

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

# ==========================================
# API های جدید مخصوص مدیریت شیفت‌های یک کارگر
# ==========================================
@router.post("/{employee_id}/shifts", response_model=EmployeeShiftResponse)
def add_employee_shift(employee_id: int, shift: EmployeeShiftCreate, db: Session = Depends(get_db)):
    db_shift = EmployeeShift(
        employee_id=employee_id,
        camera_id=shift.camera_id,
        allowed_days=shift.allowed_days,
        shift_start=shift.shift_start,
        shift_end=shift.shift_end
    )
    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)
    return db_shift

@router.delete("/shifts/{shift_id}")
def delete_employee_shift(shift_id: int, db: Session = Depends(get_db)):
    db_shift = db.query(EmployeeShift).filter(EmployeeShift.id == shift_id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    db_shift.is_deleted = True # حذف نرم شیفت
    db.commit()
    return {"status": "soft_deleted", "shift_id": shift_id}