import os
import shutil
import requests
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
                             QComboBox, QCheckBox, QTimeEdit, QGridLayout, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTime

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

# -----------------------------------------------------------------
# Thread قدرتمند برای ثبت کارگر به همراه تنظیمات شیفت
# -----------------------------------------------------------------
class AddWorkerThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str)

    def __init__(self, first_name, last_name, national_id, phone, photo_paths, shift_data):
        super().__init__()
        self.first_name = first_name
        self.last_name = last_name
        self.national_id = national_id
        self.phone = phone
        self.photo_paths = photo_paths
        self.shift_data = shift_data

    def run(self):
        try:
            full_name_persian = f"{self.first_name} {self.last_name}"
            folder_name = full_name_persian.replace(" ", "_")

            self.progress_signal.emit("در حال ثبت مشخصات متنی و شیفت کاری...")
            
            # ارسال اطلاعات کامل به بک‌اند
            payload = {
                "name": full_name_persian,
                "national_id": self.national_id,
                "phone_number": self.phone,
                "camera_id": self.shift_data["camera_id"],
                "allowed_days": self.shift_data["allowed_days"],
                "shift_start": self.shift_data["shift_start"],
                "shift_end": self.shift_data["shift_end"]
            }
            
            response = requests.post("http://localhost:8000/employees/", json=payload)
            if response.status_code != 200:
                self.finished_signal.emit(False, "خطا: سرور بک‌اند اطلاعات را قبول نکرد.")
                return

            worker_id = response.json().get("id")

            worker_folder = WORKERS_DIR / folder_name
            worker_folder.mkdir(parents=True, exist_ok=True)

            self.progress_signal.emit("در حال بارگذاری مدل هوش مصنوعی...")
            app = FaceAnalysis(name="buffalo_l")
            app.prepare(ctx_id=0)

            self.progress_signal.emit(f"در حال پردازش چهره برای {len(self.photo_paths)} عکس...")
            successful_embeddings = 0

            for idx, src_path in enumerate(self.photo_paths):
                suffix = Path(src_path).suffix.lower() or ".jpg"
                dest_filename = f"face{idx + 1}{suffix}"
                dest_path = worker_folder / dest_filename
                
                shutil.copy(src_path, dest_path)
                
                img = cv2.imread(str(dest_path))
                if img is None: continue

                faces = app.get(img)
                if len(faces) == 0: continue

                embedding_list = faces[0].embedding.tolist()
                emb_payload = {"embedding": embedding_list, "image_path": str(dest_path)}
                
                emb_res = requests.post(f"http://localhost:8000/employees/{worker_id}/embeddings", json=emb_payload)
                if emb_res.status_code == 200:
                    successful_embeddings += 1

            self.finished_signal.emit(True, f"کارگر با موفقیت ثبت شد!\nآیدی: {worker_id}\nتعداد {successful_embeddings} چهره پردازش گردید.")

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
        self.cameras_map = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 20, 40, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignTop)

        title_label = QLabel("ثبت مشخصات و افزودن چهره کارگر جدید")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title_label)

        # ----------------- 1. فرم اطلاعات هویتی -----------------
        form_layout = QFormLayout()
        self.input_first_name = QLineEdit()
        self.input_last_name = QLineEdit()
        self.input_national_id = QLineEdit()
        self.input_phone = QLineEdit()

        form_layout.addRow("نام کارگر:", self.input_first_name)
        form_layout.addRow("نام خانوادگی:", self.input_last_name)
        form_layout.addRow("کد ملی:", self.input_national_id)
        form_layout.addRow("تلفن همراه:", self.input_phone)
        main_layout.addLayout(form_layout)

        # ----------------- 2. تنظیمات شیفت و دسترسی -----------------
        shift_group = QGroupBox("دسترسی دوربین و شیفت کاری (الزامی)")
        shift_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2980b9; border: 1px solid #bdc3c7; padding: 15px; margin-top: 10px; }")
        shift_layout = QFormLayout(shift_group)

        # دوربین
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("همه دوربین‌های سالن تولید (بدون محدودیت)", None)
        shift_layout.addRow("دوربین مجاز:", self.combo_camera)

        # روزهای هفته (دوشنبه=0 تا یکشنبه=6 طبق استاندارد پایتون)
        self.days_checkboxes = {}
        days_mapping = [
            (5, "شنبه"), (6, "یک‌شنبه"), (0, "دوشنبه"), 
            (1, "سه‌شنبه"), (2, "چهارشنبه"), (3, "پنج‌شنبه"), (4, "جمعه")
        ]
        
        days_layout = QGridLayout()
        row, col = 0, 0
        for day_val, day_name in days_mapping:
            chk = QCheckBox(day_name)
            chk.setChecked(True) if day_val != 4 else chk.setChecked(False) # جمعه پیش‌فرض تعطیل است
            self.days_checkboxes[day_val] = chk
            days_layout.addWidget(chk, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        shift_layout.addRow("روزهای مجاز تردد:", days_layout)

        # ساعات شیفت
        time_layout = QHBoxLayout()
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm")
        self.time_start.setTime(QTime(8, 0)) # پیش‌فرض 08:00
        
        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat("HH:mm")
        self.time_end.setTime(QTime(17, 0)) # پیش‌فرض 17:00

        time_layout.addWidget(QLabel("از ساعت:"))
        time_layout.addWidget(self.time_start)
        time_layout.addSpacing(20)
        time_layout.addWidget(QLabel("تا ساعت:"))
        time_layout.addWidget(self.time_end)
        time_layout.addStretch()
        
        shift_layout.addRow("ساعت مجاز شیفت:", time_layout)
        main_layout.addWidget(shift_group)

        # ----------------- 3. بخش عکس و ثبت -----------------
        photo_section = QHBoxLayout()
        self.btn_select_photos = QPushButton("📸 انتخاب عکس‌های چهره...")
        self.btn_select_photos.setStyleSheet("background-color: #34495e; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_select_photos.clicked.connect(self.choose_photos_dialog)
        
        self.lbl_photos_status = QLabel("هیچ عکسی انتخاب نشده است.")
        self.btn_clear_photos = QPushButton("حذف عکس‌ها 🗑")
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

        self.btn_submit = QPushButton("💾 ذخیره کارگر و تنظیمات شیفت")
        self.btn_submit.setStyleSheet("background-color: #2ecc71; color: white; font-size: 15px; font-weight: bold; padding: 12px; border-radius: 5px;")
        self.btn_submit.clicked.connect(self.submit_form_data)
        main_layout.addWidget(self.btn_submit)

        self.load_active_cameras()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_active_cameras()

    def load_active_cameras(self):
        """دریافت دوربین‌ها از بک‌اند برای نمایش در کومبوباکس"""
        try:
            res = requests.get("http://localhost:8000/cameras/")
            if res.status_code == 200:
                self.combo_camera.clear()
                self.combo_camera.addItem("بدون محدودیت (ثبت در همه دوربین‌ها)", None)
                for cam in res.json():
                    if cam.get("is_active", True):
                        cam_name = cam.get("name", f"دوربین {cam['id']}")
                        self.combo_camera.addItem(f"{cam_name} (ID: {cam['id']})", cam["id"])
        except:
            pass

    def choose_photos_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب عکس", "", "Images (*.jpg *.jpeg *.png)")
        if files:
            for f in files:
                if f not in self.selected_photos: self.selected_photos.append(f)
            self.lbl_photos_status.setText(f"{len(self.selected_photos)} عکس برای استخراج آماده است.")
            self.btn_clear_photos.setVisible(True)

    def clear_all_selected_photos(self):
        self.selected_photos.clear()
        self.lbl_photos_status.setText("هیچ عکسی انتخاب نشده است.")
        self.btn_clear_photos.setVisible(False)

    def submit_form_data(self):
        first_name = self.input_first_name.text().strip()
        last_name = self.input_last_name.text().strip()

        if not first_name or not last_name:
            QMessageBox.warning(self, "خطا در فرم", "لطفاً نام و نام خانوادگی را وارد کنید.")
            return
        if not self.selected_photos:
            QMessageBox.warning(self, "خطا در عکس‌ها", "انتخاب حداقل یک عکس الزامی است.")
            return

        # جمع‌آوری روزهای تیک‌خورده
        selected_days = []
        for day_val, chk in self.days_checkboxes.items():
            if chk.isChecked():
                selected_days.append(str(day_val))

        shift_data = {
            "camera_id": self.combo_camera.currentData(),
            "allowed_days": ",".join(selected_days),
            "shift_start": self.time_start.time().toString("HH:mm"),
            "shift_end": self.time_end.time().toString("HH:mm")
        }

        self.btn_submit.setEnabled(False)
        self.thread = AddWorkerThread(
            first_name, last_name, self.input_national_id.text().strip(), 
            self.input_phone.text().strip(), self.selected_photos, shift_data
        )
        self.thread.progress_signal.connect(self.lbl_loading.setText)
        self.thread.finished_signal.connect(self.on_registration_finished)
        self.thread.start()

    def on_registration_finished(self, success, message):
        self.btn_submit.setEnabled(True)
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