import cv2
import numpy as np
from numpy.linalg import norm
from insightface.app import FaceAnalysis
from datetime import datetime

class ArcFaceRecognizer:
    def __init__(
        self,
        api_client,
        device="cuda",
        similarity_threshold=0.45
    ):
        self.api_client = api_client
        self.similarity_threshold = similarity_threshold
        self.known_embeddings = {}

        ctx_id = 0 if device == "cuda" else -1

        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider"] if device == "cuda" else ["CPUExecutionProvider"]
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        self.load_workers()

    def get_face_and_embedding(self, image):
        if image is None or image.size == 0:
            return None, None

        try:
            faces = self.app.get(image)
            if len(faces) == 0:
                return None, None

            best_face = max(
                faces,
                key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
            )

            embedding = best_face.embedding
            if embedding is None:
                return best_face, None

            embedding = embedding.astype(np.float32)
            embedding /= norm(embedding)

            return best_face, embedding
        except Exception as e:
            print("[ERROR] embedding error:", e)
            return None, None

    def load_workers(self):
        print("Loading face embeddings and shift rules from API...")
        try:
            # دریافت همزمان بردارها و اطلاعات شیفت کارگران
            workers_embs = self.api_client.get_all_embeddings()
            employees = self.api_client.get_employees()

            if not workers_embs:
                print("[WARNING] No embeddings received from API")
                return

            # ساخت یک دیکشنری سریع برای دسترسی به اطلاعات کارگر با آیدی
            emp_dict = {emp["id"]: emp for emp in employees}

            self.known_embeddings.clear()

            for item in workers_embs:
                employee_id = item["employee_id"]
                name = item["name"]
                emb_list = item["embedding"]

                emb = np.array(emb_list, dtype=np.float32)
                emb /= norm(emb)

                emp_info = emp_dict.get(employee_id, {})

                self.known_embeddings[employee_id] = {
                    "name": name,
                    "embedding": emb,
                    "camera_id": emp_info.get("camera_id"),
                    "allowed_days": emp_info.get("allowed_days", "0,1,2,3,4,5,6"),
                    "shift_start": emp_info.get("shift_start", "00:00"),
                    "shift_end": emp_info.get("shift_end", "23:59")
                }

            print(f"Loaded {len(self.known_embeddings)} workers with shift rules.")

        except Exception as e:
            print("[ERROR] Failed to load embeddings or employees:", e)

    # --- الگوریتم تشخیص مجاز بودن شیفت و دوربین (نسخه ضد کِرَش) ---
    def _is_allowed(self, data, current_camera_id):
        # 1. فیلتر دوربین
        if data["camera_id"] is not None and str(data["camera_id"]) != str(current_camera_id):
            return False

        now = datetime.now()
        current_day = str(now.weekday()) # 0=دوشنبه تا 6=یکشنبه

        # 2. فیلتر روزهای مجاز (استفاده از or برای فرار از مقدار None)
        allowed_days = data.get("allowed_days") or "0,1,2,3,4,5,6"
        if current_day not in allowed_days.split(","):
            return False

        # 3. فیلتر ساعت مجاز (استفاده از or برای فرار از مقدار None)
        current_time = now.strftime("%H:%M")
        start = data.get("shift_start") or "00:00"
        end = data.get("shift_end") or "23:59"

        if start <= end: # شیفت عادی
            if not (start <= current_time <= end):
                return False
        else: # شیفت شب
            if not (current_time >= start or current_time <= end):
                return False

        return True

    def compare_embedding(self, embedding, current_camera_id):
        best_score = -1
        best_id = None

        for emp_id, data in self.known_embeddings.items():
            # چک کردن مجوز قبل از مقایسه بردار (بسیار مهم برای پرفورمنس)
            if not self._is_allowed(data, current_camera_id):
                continue

            known_emb = data["embedding"]
            score = float(np.dot(embedding, known_emb))

            if score > best_score:
                best_score = score
                best_id = emp_id

        if best_id is None or best_score < self.similarity_threshold:
            return None, "unknown", float(best_score)

        return best_id, self.known_embeddings[best_id]["name"], float(best_score)

    def recognize(self, frame, body_bbox, camera_id):
        x1, y1, x2, y2 = map(int, body_bbox)

        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))

        if x2 <= x1 or y2 <= y1:
            return {"name": "unknown", "employee_id": None, "confidence": 0, "face_bbox": None}

        crop = frame[y1:y2, x1:x2]
        face, embedding = self.get_face_and_embedding(crop)

        if face is None:
            return {"name": "unknown", "employee_id": None, "confidence": 0, "face_bbox": None}

        fx1, fy1, fx2, fy2 = face.bbox.astype(int)
        fx1 += x1
        fy1 += y1
        fx2 += x1
        fy2 += y1

        # پاس دادن آیدی دوربین به تابع مقایسه
        emp_id, name, confidence = self.compare_embedding(embedding, camera_id)

        return {
            "name": name if emp_id is not None else "unknown",
            "employee_id": emp_id,
            "confidence": confidence,
            "face_bbox": [fx1, fy1, fx2, fy2]
        }