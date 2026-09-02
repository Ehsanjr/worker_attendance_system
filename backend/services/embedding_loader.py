import os
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from database import SessionLocal
from models.employee import Employee
from models.face_embedding import FaceEmbedding


# مسیر پوشه workers
BASE_DIR = Path(__file__).resolve().parents[2]
WORKERS_DIR = BASE_DIR / "data" / "workers"


# مدل تشخیص چهره
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
mtcnn = MTCNN(keep_all=False, device=_device)
resnet = InceptionResnetV1(pretrained="vggface2").eval().to(_device)

def extract_embedding(image_path):
    with open(image_path, "rb") as f:
        file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)    
    if img is None:
        return None
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    face_tensor = mtcnn(pil_img)
    if face_tensor is None:
        return None
    with torch.no_grad():
        embedding = resnet(face_tensor.unsqueeze(0).to(_device)).cpu().numpy()[0]
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
