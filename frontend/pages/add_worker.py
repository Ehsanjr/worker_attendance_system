import os
import shutil
import requests
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# مسیر ریشه پروژه (سه پوشه به عقب)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

# -----------------------------------------------------------------
# Thread قدرتمند برای ثبت کارگر، کپی تصاویر و استخراج هوش مصنوعی
# -----------------------------------------------------------------
class AddWorkerThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str) # سیگنال جدید برای گزارش وضعیت به کاربر

    def __init__(self, first_name, last_name, national_id, phone, photo_paths):
        super().__init__()
        self.first_name = first_name
        self.last_name = last_name
        self.national_id = national_id
        self.phone = phone
        self.photo_paths = photo_paths

    def run(self):
        try:
            full_name_persian = f"{self.first_name} {self.last_name}"
            folder_name = f"{self.first_name}_{self.last_name}"

            # گام ۱: ثبت اطلاعات متنی در جدول employees
            self.progress_signal.emit("در حال ثبت مشخصات متنی در دیتابیس...")
            payload = {
                "name": full_name_persian,
                "national_id": self.national_id,
                "phone_number": self.phone
            }
            
            response = requests.post("http://localhost:8000/employees/", json=payload)
            if response.status_code != 200:
                self.finished_signal.emit(False, "خطا: سرور بک‌اند اطلاعات متنی را قبول نکرد.")
                return

            worker_id = response.json().get("id")

            # گام ۲: ساخت پوشه
            worker_folder = WORKERS_DIR / folder_name
            worker_folder.mkdir(parents=True, exist_ok=True)

            # گام ۳: بارگذاری مدل هوش مصنوعی در مموری
            self.progress_signal.emit("در حال بارگذاری مدل هوش مصنوعی (InsightFace)...")
            app = FaceAnalysis(name="buffalo_l")
            app.prepare(ctx_id=0)

            # گام ۴: پردازش تک به تک عکس‌ها (کپی فایل + استخراج Embedding + ارسال به بک‌اند)
            self.progress_signal.emit(f"در حال پردازش چهره برای {len(self.photo_paths)} عکس...")
            successful_embeddings = 0

            for idx, src_path in enumerate(self.photo_paths):
                suffix = Path(src_path).suffix.lower()
                if not suffix:
                    suffix = ".jpg"
                
                dest_filename = f"face{idx + 1}{suffix}"
                dest_path = worker_folder / dest_filename
                
                # کپی عکس به پوشه
                shutil.copy(src_path, dest_path)
                
                # خواندن عکس توسط OpenCV
                img = cv2.imread(str(dest_path))
                if img is None:
                    continue

                # استخراج چهره
                faces = app.get(img)
                if len(faces) == 0:
                    print(f"Warning: No face detected in {dest_filename}")
                    continue

                # گرفتن Embedding اولین چهره داخل عکس
                embedding_list = faces[0].embedding.tolist()

                # ارسال به جدول face_embeddings
                emb_payload = {
                    "embedding": embedding_list,
                    "image_path": str(dest_path)
                }
                
                emb_res = requests.post(f"http://localhost:8000/employees/{worker_id}/embeddings", json=emb_payload)
                if emb_res.status_code == 200:
                    successful_embeddings += 1

            self.finished_signal.emit(
                True, 
                f"کارگر با موفقیت ثبت شد!\nآیدی: {worker_id}\nتعداد {successful_embeddings} چهره با موفقیت استخراج و در دیتابیس ذخیره گردید."
            )

        except Exception as e:
            self.finished_signal.emit(False, f"خطای غیرمنتظره در فرآیند ثبت‌نام:\n{str(e)}")

# -----------------------------------------------------------------
# کلاس اصلی رابط کاربری صفحه افزودن کارگر
# -----------------------------------------------------------------
class AddWorkerPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.selected_photos = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignTop)

        title_label = QLabel("ثبت مشخصات و افزودن چهره کارگر جدید")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.input_first_name = QLineEdit()
        self.input_first_name.setPlaceholderText("مثال: احسان")
        self.input_last_name = QLineEdit()
        self.input_last_name.setPlaceholderText("مثال: حسینی")
        self.input_national_id = QLineEdit()
        self.input_national_id.setPlaceholderText("کد ملی ۱۰ رقمی کارگر")
        self.input_phone = QLineEdit()
        self.input_phone.setPlaceholderText("مثال: 09123456789")

        form_layout.addRow("نام کارگر:", self.input_first_name)
        form_layout.addRow("نام خانوادگی:", self.input_last_name)
        form_layout.addRow("کد ملی:", self.input_national_id)
        form_layout.addRow("تلفن همراه:", self.input_phone)
        
        main_layout.addLayout(form_layout)

        photo_section = QHBoxLayout()
        self.btn_select_photos = QPushButton("📸 انتخاب عکس‌های چهره...")
        self.btn_select_photos.setStyleSheet("background-color: #34495e; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_select_photos.clicked.connect(self.choose_photos_dialog)
        
        self.lbl_photos_status = QLabel("هیچ عکسی انتخاب نشده است.")
        self.lbl_photos_status.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 13px;")

        self.btn_clear_photos = QPushButton("حذف عکس‌ها 🗑")
        self.btn_clear_photos.setStyleSheet("background-color: #bdc3c7; color: #7f8c8d; padding: 5px;")
        self.btn_clear_photos.setVisible(False)
        self.btn_clear_photos.clicked.connect(self.clear_all_selected_photos)

        photo_section.addWidget(self.btn_select_photos)
        photo_section.addWidget(self.lbl_photos_status)
        photo_section.addWidget(self.btn_clear_photos)
        photo_section.addStretch()
        
        main_layout.addLayout(photo_section)

        self.lbl_loading = QLabel("")
        self.lbl_loading.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 13px;")
        self.lbl_loading.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_loading)

        self.btn_submit = QPushButton("💾 ذخیره و پردازش هوش مصنوعی")
        self.btn_submit.setStyleSheet("""
            background-color: #2ecc71; 
            color: white; 
            font-size: 15px; 
            font-weight: bold; 
            padding: 12px; 
            border-radius: 5px;
        """)
        self.btn_submit.clicked.connect(self.submit_form_data)
        main_layout.addWidget(self.btn_submit)

    def choose_photos_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "انتخاب عکس‌های چهره کارگر", "", "Images (*.jpg *.jpeg *.png)"
        )
        if files:
            for f in files:
                if f not in self.selected_photos:
                    self.selected_photos.append(f)
            
            self.lbl_photos_status.setText(f"تعداد {len(self.selected_photos)} عکس برای استخراج چهره آماده است.")
            self.lbl_photos_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.btn_clear_photos.setVisible(True)

    def clear_all_selected_photos(self):
        self.selected_photos.clear()
        self.lbl_photos_status.setText("هیچ عکسی انتخاب نشده است.")
        self.lbl_photos_status.setStyleSheet("color: #7f8c8d; font-weight: bold;")
        self.btn_clear_photos.setVisible(False)

    def submit_form_data(self):
        first_name = self.input_first_name.text().strip()
        last_name = self.input_last_name.text().strip()
        national_id = self.input_national_id.text().strip()
        phone = self.input_phone.text().strip()

        if not first_name or not last_name or not national_id or not phone:
            QMessageBox.warning(self, "خطا در فرم", "لطفاً تمامی فیلدهای متنی را پر کنید.")
            return

        if not self.selected_photos:
            QMessageBox.warning(self, "خطا در عکس‌ها", "لطفاً حداقل یک عکس برای استخراج چهره انتخاب کنید.")
            return

        self.btn_submit.setEnabled(False)
        self.btn_select_photos.setEnabled(False)
        
        self.thread = AddWorkerThread(first_name, last_name, national_id, phone, self.selected_photos)
        # اتصال سیگنال‌ها
        self.thread.progress_signal.connect(self.lbl_loading.setText)
        self.thread.finished_signal.connect(self.on_registration_finished)
        self.thread.start()

    def on_registration_finished(self, success, message):
        self.btn_submit.setEnabled(True)
        self.btn_select_photos.setEnabled(True)
        self.lbl_loading.setText("")

        if success:
            QMessageBox.information(self, "عملیات موفق", message)
            self.input_first_name.clear()
            self.input_last_name.clear()
            self.input_national_id.clear()
            self.input_phone.clear()
            self.clear_all_selected_photos()
        else:
            QMessageBox.critical(self, "خطای سیستم", message)