from fastapi import FastAPI
from database import engine, Base

# مهم ✅ — این‌ها باعث می‌شوند جدول‌ها ساخته شوند
import models.employee
import models.camera
import models.attendance_event
import models.face_embedding

from routers import employees
from routers import cameras
from routers import attendance
from routers import ai_events

app = FastAPI()

# ✅ ساخت جدول‌ها
Base.metadata.create_all(bind=engine)

app.include_router(employees.router)
app.include_router(cameras.router)
app.include_router(attendance.router)
app.include_router(ai_events.router)
