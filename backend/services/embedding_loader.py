import os
from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

from database import SessionLocal
from models.employee import Employee
from models.face_embedding import FaceEmbedding


# مسیر پوشه workers
BASE_DIR = Path(__file__).resolve().parents[2]
WORKERS_DIR = BASE_DIR / "data" / "workers"


# مدل تشخیص چهره
app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0)


def extract_embedding(image_path):

    img = cv2.imread(str(image_path))

    if img is None:
        return None

    faces = app.get(img)

    if len(faces) == 0:
        return None

    face = faces[0]

    embedding = face.embedding

    return embedding


def process_workers():

    db = SessionLocal()

    for worker_name in os.listdir(WORKERS_DIR):

        worker_path = WORKERS_DIR / worker_name

        if not worker_path.is_dir():
            continue

        print(f"\nProcessing worker: {worker_name}")

        employee = Employee(name=worker_name)

        db.add(employee)
        db.commit()
        db.refresh(employee)

        for img_name in os.listdir(worker_path):

            img_path = worker_path / img_name

            if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
                continue

            embedding = extract_embedding(img_path)

            if embedding is None:
                print(f"Face not detected: {img_name}")
                continue

            embedding_list = embedding.tolist()

            face_embedding = FaceEmbedding(
                employee_id=employee.id,
                embedding=embedding_list,
                image_path=str(img_path)
            )

            db.add(face_embedding)

            print(f"Added embedding for {img_name}")

        db.commit()

    db.close()

    print("\n✅ All workers processed successfully.")


if __name__ == "__main__":
    process_workers()
