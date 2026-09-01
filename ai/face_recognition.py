import threading
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

        # 🔴 FIX (CUBLAS resource-allocation crash):
        # insightface/onnxruntime با provider CUDA برای فراخوانی‌های *همزمان*
        # از چند Thread مختلف thread-safe نیست. `live_dashboard.py` چند دوربین
        # را با ThreadPoolExecutor موازی پردازش می‌کند و همه‌شان همین یک
        # instance از ArcFaceRecognizer (و همین یک CUDA context) را صدا می‌زنند.
        # وقتی دو Thread هم‌زمان وارد onnxruntime بشوند، ساختِ cuBLAS handle
        # شکست می‌خورد -> دقیقاً همان ارور:
        #   "CUBLAS failure 3: the resource allocation failed ; cublasCreate"
        # راه‌حل: یک قفل فقط دورِ خودِ فراخوانیِ مدل (self.app.get). بقیه‌ی کارِ
        # هر Thread (I/O، پردازش قبل/بعد) همچنان موازی می‌ماند؛ فقط عبورِ واقعی
        # از GPU سریالی می‌شود که دقیقاً چیزی‌ست که یک CUDA context مشترک
        # نیاز دارد.
        self._infer_lock = threading.Lock()

        self.device = device
        self._init_face_app(device)

        self.load_workers()

    def _init_face_app(self, device):
        """
        🔴 راه‌اندازیِ FaceAnalysis با fallback امن: اگر GPU/CUDA به هر دلیلی
        (کمبود VRAM، ناسازگاریِ نسخه‌ی onnxruntime-gpu با درایور/CUDA نصب‌شده،
        دراگ استفاده‌ی هم‌زمانِ YOLO+insightface از GPU و...) بالا نیاید، به‌جای
        کرش کاملِ برنامه، روی CPU سوییچ می‌کنیم و برنامه به کار خودش ادامه
        می‌دهد (کندتر ولی زنده).
        """
        want_cuda = device == "cuda"
        providers = ["CUDAExecutionProvider"] if want_cuda else ["CPUExecutionProvider"]

        try:
            self.app = FaceAnalysis(name="buffalo_l", providers=providers)
            self.app.prepare(ctx_id=0 if want_cuda else -1, det_size=(640, 640))
            self.device = "cuda" if want_cuda else "cpu"
        except Exception as e:
            if want_cuda:
                print(f"[WARNING] راه‌اندازیِ CUDA برای چهره‌یابی شکست خورد ({e})؛ "
                      f"سوییچ به CPU. برای رفع اصلِ مشکل، نسخه‌ی onnxruntime-gpu "
                      f"و درایور/CUDA/cuDNN نصب‌شده روی سیستم را چک کنید (باید هم‌خوان باشند) "
                      f"و مطمئن شوید VRAM کافی برای YOLO+insightface هم‌زمان وجود دارد.")
                self.app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                self.app.prepare(ctx_id=-1, det_size=(640, 640))
                self.device = "cpu"
            else:
                raise

    def get_face_and_embedding(self, image):
        if image is None or image.size == 0:
            return None, None

        try:
            with self._infer_lock:  # 🔴 سریالی‌کردنِ فراخوانیِ GPU
                faces = self.app.get(image)

            if len(faces) == 0:
                return None, None

            h_img, w_img = image.shape[:2]
            crop_center_x = w_img / 2.0

            def face_score(f):
                fx1, fy1, fx2, fy2 = f.bbox
                area = max(0.0, fx2 - fx1) * max(0.0, fy2 - fy1)
                face_center_x = (fx1 + fx2) / 2.0
                horizontal_offset = abs(face_center_x - crop_center_x) / (w_img / 2.0 + 1e-6)
                horizontal_offset = min(horizontal_offset, 1.0)
                return area * (1.0 - 0.85 * horizontal_offset)

            best_face = max(faces, key=face_score)

            embedding = best_face.embedding
            if embedding is None:
                return best_face, None

            embedding = embedding.astype(np.float32)
            n = norm(embedding)
            if n == 0:
                return best_face, None
            embedding /= n

            return best_face, embedding
        except Exception as e:
            print("[ERROR] embedding error:", e)
            return None, None

    def load_workers(self):
        print("Loading face embeddings and shift rules from API...")
        try:
            workers_embs = self.api_client.get_all_embeddings()
            employees = self.api_client.get_employees()

            if not workers_embs:
                print("[WARNING] No embeddings received from API")
                return

            emp_dict = {emp["id"]: emp for emp in employees}
            self.known_embeddings.clear()

            skipped = 0
            for item in workers_embs:
                employee_id = item["employee_id"]
                if employee_id not in emp_dict:
                    skipped += 1
                    continue

                name = item["name"]
                emb_list = item["embedding"]

                emb = np.array(emb_list, dtype=np.float32)
                emb /= norm(emb)

                emp_info = emp_dict.get(employee_id, {})

                # 🔴 دریافت تمام شیفت‌های فعالِ این کارگر
                active_shifts = [s for s in emp_info.get("shifts", []) if not s.get("is_deleted", False)]

                # 🔴 هر کارگر ممکن است چند تصویر/امبدینگ داشته باشد (از جمله نسخه‌های degraded).
                # همه‌ی امبدینگ‌ها نگه داشته می‌شوند، نه فقط آخرین موردی که پردازش می‌شود.
                if employee_id not in self.known_embeddings:
                    self.known_embeddings[employee_id] = {
                        "name": name,
                        "embeddings": [],
                        "shifts": active_shifts
                    }
                self.known_embeddings[employee_id]["embeddings"].append(emb)

            total_samples = sum(len(v["embeddings"]) for v in self.known_embeddings.values())
            print(f"Loaded {len(self.known_embeddings)} workers "
                  f"({total_samples} face samples total) with shift rules.")
            if skipped:
                print(f"[WARNING] {skipped} embedding rows skipped "
                      f"(employee_id not found in /employees/)")

        except Exception as e:
            print("[ERROR] Failed to load embeddings or employees:", e)

    # --- الگوریتم تشخیص مجاز بودن شیفت و دوربین (نسخه ضد کِرَش) ---
    def _is_allowed(self, data, current_camera_id):
        shifts = data.get("shifts", [])

        # اگر کارگر هیچ شیفتی ندارد، یعنی فعلاً اجازه ورود به هیچ دوربینی را ندارد
        if not shifts:
            return False

        now = datetime.now()
        current_day = str(now.weekday())
        current_time = now.strftime("%H:%M")

        for shift in shifts:
            # 1. فیلتر دوربین
            if shift["camera_id"] is not None and str(shift["camera_id"]) != str(current_camera_id):
                continue

            # 2. فیلتر روزهای مجاز
            allowed_days = shift.get("allowed_days") or "0,1,2,3,4,5,6"
            if current_day not in allowed_days.split(","):
                continue

            # 3. فیلتر ساعت مجاز
            start = shift.get("shift_start") or "00:00"
            end = shift.get("shift_end") or "23:59"

            if start <= end:  # شیفت عادی
                if start <= current_time <= end:
                    return True
            else:  # شیفت شب
                if current_time >= start or current_time <= end:
                    return True

        return False

    def compare_embedding(self, embedding, current_camera_id):
        best_score = -1
        best_id = None

        # 🔴 مقایسه با تمام کارگرهای شناخته‌شده، بدون فیلتر شیفت. شناسایی هویت
        # باید مستقل از مجاز بودن باشد.
        for emp_id, data in self.known_embeddings.items():
            samples = data.get("embeddings", [])
            if not samples:
                continue
            emp_best = max(float(np.dot(embedding, known_emb)) for known_emb in samples)

            if emp_best > best_score:
                best_score = emp_best
                best_id = emp_id

        if best_id is None or best_score < self.similarity_threshold:
            closest_name = self.known_embeddings.get(best_id, {}).get("name", "هیچ‌کدام") if best_id else "هیچ‌کدام"
            print(f"[DEBUG] نزدیک‌ترین تطابق: {closest_name} | امتیاز: {best_score:.3f} | آستانه: {self.similarity_threshold}")
            return None, "unknown", float(best_score), False

        is_authorized = self._is_allowed(self.known_embeddings[best_id], current_camera_id)

        return best_id, self.known_embeddings[best_id]["name"], float(best_score), is_authorized

    def recognize(self, frame, body_bbox, camera_id):
        """
        چهره‌یابی روی کراپِ باکسِ بدنِ یک نفر (نه کل فریم). برای هر باکسِ بدن
        جداگانه صدا زده می‌شود.

        نکته: camera_id الزامی است (برای چک شیفت/مجاز بودن).
        """
        x1, y1, x2, y2 = map(int, body_bbox)

        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))

        if x2 <= x1 or y2 <= y1:
            return {"name": "unknown", "employee_id": None, "confidence": 0, "face_bbox": None, "shift_ok": False}

        box_w = x2 - x1
        margin = int(box_w * 0.12)
        fx1_crop = x1 + margin if (x2 - margin) > (x1 + margin) else x1
        fx2_crop = x2 - margin if (x2 - margin) > (x1 + margin) else x2

        crop = frame[y1:y2, fx1_crop:fx2_crop]
        face, embedding = self.get_face_and_embedding(crop)

        if face is None or embedding is None:
            return {"name": "unknown", "employee_id": None, "confidence": 0, "face_bbox": None, "shift_ok": False}

        fx1, fy1, fx2, fy2 = face.bbox.astype(int)
        fx1 += fx1_crop
        fy1 += y1
        fx2 += fx1_crop
        fy2 += y1

        emp_id, name, confidence, shift_ok = self.compare_embedding(embedding, camera_id)

        return {
            "name": name if emp_id is not None else "unknown",
            "employee_id": emp_id,
            "confidence": confidence,
            "face_bbox": [fx1, fy1, fx2, fy2],
            "shift_ok": shift_ok
        }

    def detect_and_recognize(self, frame, camera_id):
        """
        چهره‌یابی مستقیم روی کل فریم (نه کراپ از باکس بدن هر نفر).
        خروجی: لیستی از دیکشنری، هرکدام برای یک چهره‌ی واقعاً دیده‌شده در فریم.

        🔴 این تابع ممکن است از چند Thread مختلف هم‌زمان صدا زده شود
        (ThreadPoolExecutor در live_dashboard.py). فراخوانیِ واقعیِ مدل با
        self._infer_lock سریالی می‌شود تا با CUDA/onnxruntime تداخل نکند.
        """
        results = []
        if frame is None or frame.size == 0:
            return results

        try:
            with self._infer_lock:  # 🔴 سریالی‌کردنِ فراخوانیِ GPU
                faces = self.app.get(frame)
        except Exception as e:
            print("[ERROR] face detection error:", e)
            return results

        for face in faces:
            embedding = face.embedding
            if embedding is None:
                continue

            embedding = embedding.astype(np.float32)
            n = norm(embedding)
            if n == 0:
                continue
            embedding = embedding / n

            emp_id, name, confidence, shift_ok = self.compare_embedding(embedding, camera_id)
            fx1, fy1, fx2, fy2 = face.bbox.astype(int)

            results.append({
                "name": name if emp_id is not None else "unknown",
                "employee_id": emp_id,
                "confidence": confidence,
                "face_bbox": [int(fx1), int(fy1), int(fx2), int(fy2)],
                "shift_ok": shift_ok
            })

        return results