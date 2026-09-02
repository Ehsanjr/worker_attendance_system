import sys
from pathlib import Path

# 🔴 FIX: این فایل داخلِ backend/services/ است؛ برای اینکه import های
# "backend.xxx" کار کنن، باید ریشه‌ی پروژه (دو پوشه بالاتر) به sys.path
# اضافه بشه — چون وقتی مستقیم این فایل اجرا میشه، پایتون فقط پوشه‌ی
# خودِ فایل رو به sys.path اضافه می‌کنه، نه ریشه‌ی پروژه رو.
BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/services/re_embed.py -> بالا بیا ۱ پوشه -> backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
from models.face_embedding import FaceEmbedding
from services.embedding_loader import extract_embedding

db = SessionLocal()
rows = db.query(FaceEmbedding).all()
for row in rows:
    new_emb = extract_embedding(row.image_path)
    if new_emb is None:
        print(f"[SKIP] چهره در {row.image_path} پیدا نشد")
        continue
    row.embedding = new_emb.tolist()
db.commit()
db.close()

success_count = 0
for row in rows:
    new_emb = extract_embedding(row.image_path)
    if new_emb is None:
        print(f"[SKIP] چهره در {row.image_path} پیدا نشد")
        continue
    row.embedding = new_emb.tolist()
    success_count += 1
db.commit()
db.close()
print(f"✅ {success_count} از {len(rows)} embedding بازسازی شد.")