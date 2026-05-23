import cv2
import numpy as np
from numpy.linalg import norm
from insightface.app import FaceAnalysis


class ArcFaceRecognizer:
    def __init__(
        self,
        api_client,
        device="cuda",
        similarity_threshold=0.45
    ):
        self.api_client = api_client
        self.similarity_threshold = similarity_threshold
        self.known_embeddings = {}   # { employee_id: {name, embedding} }

        ctx_id = 0 if device == "cuda" else -1

        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider"] if device == "cuda"
            else ["CPUExecutionProvider"]
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        self.load_workers()

    # --------------------------------------------------
    # Extract face + embedding
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Load from backend API
    # --------------------------------------------------
    def load_workers(self):
        print("Loading face embeddings from API...")

        try:
            workers = self.api_client.get_all_embeddings()

            if not workers:
                print("[WARNING] No embeddings received from API")
                return

            self.known_embeddings.clear()

            for item in workers:
                employee_id = item["employee_id"]
                name = item["name"]
                emb_list = item["embedding"]

                emb = np.array(emb_list, dtype=np.float32)
                emb /= norm(emb)

                self.known_embeddings[employee_id] = {
                    "name": name,
                    "embedding": emb
                }

                print(f"Loaded: {name} (ID={employee_id})")

        except Exception as e:
            print("[ERROR] Failed to load embeddings:", e)

    # --------------------------------------------------
    # Compare and return best match
    # --------------------------------------------------
    def compare_embedding(self, embedding):
        best_score = -1
        best_id = None

        for emp_id, data in self.known_embeddings.items():
            known_emb = data["embedding"]
            score = float(np.dot(embedding, known_emb))

            if score > best_score:
                best_score = score
                best_id = emp_id

        if best_id is None or best_score < self.similarity_threshold:
            return None, "unknown", float(best_score)

        return best_id, self.known_embeddings[best_id]["name"], float(best_score)

    # --------------------------------------------------
    # Full recognition
    # --------------------------------------------------
    def recognize(self, frame, body_bbox):
        x1, y1, x2, y2 = map(int, body_bbox)

        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))

        if x2 <= x1 or y2 <= y1:
            return {
                "name": "unknown",
                "employee_id": None,
                "confidence": 0,
                "face_bbox": None
            }

        crop = frame[y1:y2, x1:x2]

        face, embedding = self.get_face_and_embedding(crop)

        # ❌ اگر حتی صورت هم پیدا نشد
        if face is None:
            return {
                "name": "unknown",
                "employee_id": None,
                "confidence": 0,
                "face_bbox": None
            }

        # ✅ اگر صورت پیدا شد → bbox را محاسبه کن
        fx1, fy1, fx2, fy2 = face.bbox.astype(int)

        # تبدیل از crop space → global space
        fx1 += x1
        fy1 += y1
        fx2 += x1
        fy2 += y1

        # حالا برو سراغ recognition
        emp_id, name, confidence = self.compare_embedding(embedding)

        # ✅ حتی اگر unknown باشد، bbox را برگردان
        return {
            "name": name if emp_id is not None else "unknown",
            "employee_id": emp_id,
            "confidence": confidence,
            "face_bbox": [fx1, fy1, fx2, fy2]
        }


