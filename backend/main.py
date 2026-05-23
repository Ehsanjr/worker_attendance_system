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
from routers import embedding

app = FastAPI()

# ✅ ساخت جدول‌ها
print("Starting table creation...")
Base.metadata.create_all(bind=engine)
print("Tables created.")


app.include_router(employees.router)
app.include_router(cameras.router)
app.include_router(attendance.router)
app.include_router(ai_events.router)
app.include_router(embedding.router)
