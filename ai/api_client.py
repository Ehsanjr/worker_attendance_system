import requests
from datetime import datetime

class APIClient:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url

    def get_all_embeddings(self):
        try:
            response = requests.get(f"{self.base_url}/embeddings/")
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print("[API] Embedding fetch error:", e)
            return []

    def send_attendance_event(self, data):
        url = f"{self.base_url}/ai-events/"

        timestamp = data["timestamp"]

        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()

        # ایمن‌سازی camera_id برای تست‌های محلی
        camera_id = data.get("camera_id")
        if isinstance(camera_id, str):
            # اگر رشته مثل 'webcam' بود، مقدار پیش‌فرض بده
            if camera_id.lower() == "webcam":
                camera_id = 0  # یا None، بسته به schema backend
            else:
                # اگر رشته‌ی URL یا اسم دوربین است، تلاش کن عدد استخراج کنی
                camera_id = 0

        payload = {
            "employee_id": int(data["employee_id"]),
            "camera_id": int(camera_id),
            "event": data["event_type"],
            "track_id": data.get("track_id"),
            "confidence": float(data.get("confidence", 1.0)),
            "time": timestamp
        }

        try:
            response = requests.post(url, json=payload)
            if response.status_code in (200, 201):
                print("[API] event sent OK")
                return True
            else:
                print("[API] send failed:", response.text)
                return False

        except Exception as e:
            print("[API] event send error:", e)
            return False