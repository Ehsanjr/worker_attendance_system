from fastapi import APIRouter, HTTPException
from typing import List

from schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeWithEmbeddings,
)

router = APIRouter(prefix="/employees", tags=["employees"])

fake_db = []
id_counter = 1


@router.post("/", response_model=EmployeeResponse)
def create_employee(employee: EmployeeCreate):
    global id_counter

    new_employee = {
        "id": id_counter,
        "name": employee.name,
        "created_at": "2026-01-01T00:00:00"
    }

    fake_db.append(new_employee)
    id_counter += 1

    return new_employee


@router.get("/", response_model=List[EmployeeResponse])
def list_employees():
    return fake_db


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int):

    for emp in fake_db:
        if emp["id"] == employee_id:
            return emp

    raise HTTPException(status_code=404, detail="Employee not found")


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate):

    for emp in fake_db:

        if emp["id"] == employee_id:

            if data.name is not None:
                emp["name"] = data.name

            return emp

    raise HTTPException(status_code=404, detail="Employee not found")


@router.delete("/{employee_id}")
def delete_employee(employee_id: int):

    for emp in fake_db:

        if emp["id"] == employee_id:
            fake_db.remove(emp)
            return {"message": "employee deleted"}

    raise HTTPException(status_code=404, detail="Employee not found")
