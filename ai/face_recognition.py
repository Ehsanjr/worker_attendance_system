import os
import cv2
import numpy as np
from numpy.linalg import norm

from insightface.app import FaceAnalysis


class ArcFaceRecognizer:

    def __init__(
        self,
        workers_dir="../data/workers",
        device="cuda",
        similarity_threshold=0.45
    ):
        self.workers_dir = workers_dir
        self.similarity_threshold = similarity_threshold
        self.known_embeddings = {}

        ctx_id = 0 if device == "cuda" else -1

        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider"] if device == "cuda"
            else ["CPUExecutionProvider"]
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
            print("embedding error:", e)
            return None, None

    def load_workers(self):
        if not os.path.exists(self.workers_dir):
            print("workers folder not found:", self.workers_dir)
            return

        for person_name in os.listdir(self.workers_dir):
            person_path = os.path.join(self.workers_dir, person_name)

            if not os.path.isdir(person_path):
                continue

            embeddings = []

            for img_name in os.listdir(person_path):
                img_path = os.path.join(person_path, img_name)
                img = cv2.imread(img_path)

                if img is None:
                    continue

                _, emb = self.get_face_and_embedding(img)

                if emb is not None:
                    embeddings.append(emb)

            if len(embeddings) == 0:
                print(f"[WARNING] no valid images for {person_name}")
                continue

            mean_embedding = np.mean(embeddings, axis=0)
            mean_embedding = mean_embedding / norm(mean_embedding)

            self.known_embeddings[person_name] = mean_embedding
            print(f"{person_name} loaded ({len(embeddings)} images)")

    def compare_embedding(self, embedding):
        best_score = -1.0
        best_person = "unknown"

        for person_name, known_embedding in self.known_embeddings.items():
            score = float(np.dot(embedding, known_embedding))

            if score > best_score:
                best_score = score
                best_person = person_name

        if best_score < self.similarity_threshold:
            return "unknown", round(best_score, 4)

        return best_person, round(best_score, 4)

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
                "confidence": 0.0,
                "face_bbox": (x1, y1, x2, y2)
            }

        person_crop = frame[y1:y2, x1:x2]

        face, embedding = self.get_face_and_embedding(person_crop)

        if face is None:
            return {
                "name": "unknown",
                "confidence": 0.0,
                "face_bbox": (x1, y1, x2, y2)
            }

        fx1, fy1, fx2, fy2 = map(int, face.bbox)
        face_bbox = (fx1 + x1, fy1 + y1, fx2 + x1, fy2 + y1)

        if embedding is None:
            return {
                "name": "unknown",
                "confidence": 0.0,
                "face_bbox": face_bbox
            }

        name, confidence = self.compare_embedding(embedding)

        if name == "unknown":
            return {
                "name": "unknown",
                "confidence": 0.0,
                "face_bbox": face_bbox
            }

        return {
            "name": name,
            "confidence": confidence,
            "face_bbox": face_bbox
        }
