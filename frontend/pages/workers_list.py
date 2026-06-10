import requests
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QMessageBox, QDialog, QLineEdit, QFormLayout, QLabel)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QMessageBox, QDialog, QLineEdit, QFormLayout, QLabel, QStackedWidget) # این ایمپورت اضافه شد

import os
import shutil
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis
from PyQt5.QtWidgets import QFileDialog

# تعیین مسیر پوشه کارگران برای ذخیره عکس‌های جدید
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

# -----------------------------------------------------------------
# Thread برای دریافت لیست کارگران از بک‌اند
# -----------------------------------------------------------------
class FetchWorkersThread(QThread):
    workers_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            response = requests.get("http://localhost:8000/employees/")
            response.raise_for_status()
            self.workers_ready.emit(response.json())
        except Exception as e:
            self.error_occurred.emit(str(e))

# -----------------------------------------------------------------
# پنجره پاپ‌آپ نمایش رخدادهای اختصاصی یک کارگر (اصلاح نهایی)
# -----------------------------------------------------------------
class WorkerEventsDialog(QDialog):
    def __init__(self, worker_id, worker_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"تاریخچه رخدادهای حضور و غیاب - {worker_name}")
        self.resize(700, 400)
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout(self)
        
        title = QLabel(f"لیست کامل ترددهای ثبت شده برای: {worker_name} (آیدی: {worker_id})")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # استفاده از QStackedWidget برای سوئیچ کردن بین جدول و پیام خالی
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # صفحه ۱: جدول
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "آیدی رخداد", "آیدی کارگر", "موقعیت دوربین", "نوع رخداد (وضعیت)", "زمان دقیق"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stack.addWidget(self.table)
        
        # صفحه ۲: پیام خالی که در مرکز قرار می‌گیرد
        self.empty_label = QLabel("هیچ رخدادی برای این کارگر در دیتابیس ثبت نشده است.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #7f8c8d;")
        self.stack.addWidget(self.empty_label)
        
        # دکمه بستن
        close_btn = QPushButton("بستن پنجره")
        close_btn.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.load_events(worker_id)

    def load_events(self, worker_id):
        try:
            # --- بخش جدید: دریافت دوربین‌ها و ساخت دیکشنری مپینگ (آیدی به لوکیشن) ---
            camera_locations = {}
            try:
                cam_res = requests.get("http://localhost:8000/cameras/")
                if cam_res.status_code == 200:
                    for cam in cam_res.json():
                        # اگر لوکیشن خالی بود، نام دوربین را نشان بدهد
                        camera_locations[cam.get("id")] = cam.get("location") or cam.get("name") or "نامشخص"
            except:
                pass 
            # ------------------------------------------------------------------------

            response = requests.get("http://localhost:8000/attendance/")
            if response.status_code == 200:
                events = response.json()
                self.table.setRowCount(0)
                
                inserted_row_idx = 0
                for ev in events:
                    if ev.get("employee_id") is not None and int(ev["employee_id"]) == int(worker_id):
                        self.table.insertRow(inserted_row_idx)
                        
                        id_item = QTableWidgetItem(str(ev.get("id", "---")))
                        id_item.setTextAlignment(Qt.AlignCenter)
                        
                        emp_id_item = QTableWidgetItem(str(ev.get("employee_id", "---")))
                        emp_id_item.setTextAlignment(Qt.AlignCenter)
                        
                        # --- بخش تغییر یافته: جایگذاری لوکیشن دوربین ---
                        cam_id = ev.get("camera_id")
                        cam_loc = camera_locations.get(cam_id) or "لوکیشن نامشخص"
                        cam_item = QTableWidgetItem(str(cam_loc))
                        cam_item.setTextAlignment(Qt.AlignCenter)
                        # -----------------------------------------------
                        
                        status_raw = ev.get("event_type") or ev.get("status") or ev.get("type") or "---"
                        status_text = "ورود" if status_raw.upper() == "IN" else "خروج" if status_raw.upper() == "OUT" else status_raw
                        status_item = QTableWidgetItem(status_text)
                        status_item.setTextAlignment(Qt.AlignCenter)
                        
                        if status_raw.upper() == "IN":
                            status_item.setStyleSheet("color: #2ecc71; font-weight: bold;")
                        elif status_raw.upper() == "OUT":
                            status_item.setStyleSheet("color: #e74c3c; font-weight: bold;")
                        
                        time_str = ev.get("timestamp", "---").replace("T", "  ").split(".")[0]
                        time_item = QTableWidgetItem(time_str)
                        time_item.setTextAlignment(Qt.AlignCenter)

                        self.table.setItem(inserted_row_idx, 0, id_item)
                        self.table.setItem(inserted_row_idx, 1, emp_id_item)
                        self.table.setItem(inserted_row_idx, 2, cam_item)
                        self.table.setItem(inserted_row_idx, 3, status_item)
                        self.table.setItem(inserted_row_idx, 4, time_item)
                        
                        inserted_row_idx += 1
                
                if inserted_row_idx == 0:
                    self.stack.setCurrentIndex(1)
                else:
                    self.stack.setCurrentIndex(0)
            else:
                self.stack.setCurrentIndex(1)
        except Exception:
            self.stack.setCurrentIndex(1)

# -----------------------------------------------------------------
# Thread برای آپدیت اطلاعات و افزودن عکس‌های جدید در پس‌زمینه
# -----------------------------------------------------------------
class EditWorkerThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str)

    def __init__(self, worker_id, original_name, updated_data, new_photo_paths):
        super().__init__()
        self.worker_id = worker_id
        self.original_name = original_name
        self.updated_data = updated_data
        self.new_photo_paths = new_photo_paths

    def run(self):
        try:
            # ۱. ارسال اطلاعات متنی آپدیت شده به بک‌اند
            self.progress_signal.emit("در حال به‌روزرسانی اطلاعات متنی...")
            update_res = requests.put(f"http://localhost:8000/employees/{self.worker_id}", json=self.updated_data)
            
            if update_res.status_code != 200:
                self.finished_signal.emit(False, "خطا در ویرایش اطلاعات متنی در سرور.")
                return

            # ۲. اگر عکس جدیدی انتخاب نشده بود، همینجا کار تمام است
            if not self.new_photo_paths:
                self.finished_signal.emit(True, "اطلاعات کارگر با موفقیت ویرایش شد.")
                return

            # ۳. پردازش عکس‌های جدید
            self.progress_signal.emit("در حال بارگذاری هوش مصنوعی برای عکس‌های جدید...")
            
            # پیدا کردن پوشه کارگر (با جایگزینی فاصله با خط‌تیره طبق استاندارد ثبت‌نام)
            folder_name = self.original_name.replace(" ", "_")
            worker_folder = WORKERS_DIR / folder_name
            worker_folder.mkdir(parents=True, exist_ok=True)

            # پیدا کردن آخرین شماره عکس (faceN) برای ادامه نام‌گذاری
            existing_faces = [f for f in os.listdir(worker_folder) if f.startswith("face")]
            max_n = 0
            for f in existing_faces:
                try:
                    num = int(''.join(filter(str.isdigit, f)))
                    if num > max_n: max_n = num
                except: pass
            
            current_idx = max_n + 1

            app = FaceAnalysis(name="buffalo_l")
            app.prepare(ctx_id=0)

            self.progress_signal.emit(f"در حال استخراج و ذخیره {len(self.new_photo_paths)} چهره جدید...")
            successful_embeddings = 0

            for src_path in self.new_photo_paths:
                suffix = Path(src_path).suffix.lower() or ".jpg"
                dest_filename = f"face{current_idx}{suffix}"
                dest_path = worker_folder / dest_filename
                
                shutil.copy(src_path, dest_path)
                
                img = cv2.imread(str(dest_path))
                if img is not None:
                    faces = app.get(img)
                    if len(faces) > 0:
                        embedding_list = faces[0].embedding.tolist()
                        emb_payload = {
                            "embedding": embedding_list,
                            "image_path": str(dest_path)
                        }
                        emb_res = requests.post(f"http://localhost:8000/employees/{self.worker_id}/embeddings", json=emb_payload)
                        if emb_res.status_code == 200:
                            successful_embeddings += 1
                
                current_idx += 1

            self.finished_signal.emit(True, f"ویرایش موفق!\nتعداد {successful_embeddings} عکس جدید هم پردازش و اضافه شد.")

        except Exception as e:
            self.finished_signal.emit(False, f"خطای سیستمی هنگام ویرایش:\n{str(e)}")


# -----------------------------------------------------------------
# دیالوگ پاپ‌آپ برای ویرایش اطلاعات و افزودن عکس جدید
# -----------------------------------------------------------------
class EditWorkerDialog(QDialog):
    def __init__(self, worker_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ویرایش اطلاعات کارگر")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.worker_id = worker_data["id"]
        self.original_name = worker_data["name"]
        self.new_photos = []

        layout = QFormLayout(self)
        layout.setSpacing(15)

        self.name_input = QLineEdit(worker_data["name"])
        self.national_id_input = QLineEdit(worker_data.get("national_id") or "")
        self.phone_input = QLineEdit(worker_data.get("phone_number") or "")

        layout.addRow("نام و نام خانوادگی:", self.name_input)
        layout.addRow("کد ملی:", self.national_id_input)
        layout.addRow("تلفن همراه:", self.phone_input)

        # بخش انتخاب عکس جدید
        photo_layout = QHBoxLayout()
        self.btn_add_photo = QPushButton("➕ افزودن عکس جدید")
        self.btn_add_photo.setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        self.btn_add_photo.clicked.connect(self.select_new_photos)
        
        self.lbl_photo_status = QLabel("بدون عکس جدید")
        self.lbl_photo_status.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        
        photo_layout.addWidget(self.btn_add_photo)
        photo_layout.addWidget(self.lbl_photo_status)
        photo_layout.addStretch()
        layout.addRow("تکمیل چهره:", photo_layout)

        # لیبل وضعیت پردازش
        self.lbl_loading = QLabel("")
        self.lbl_loading.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 12px;")
        self.lbl_loading.setAlignment(Qt.AlignCenter)
        layout.addRow(self.lbl_loading)

        # دکمه‌ها
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("ذخیره تغییرات")
        self.save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px;")
        self.save_btn.clicked.connect(self.start_saving_process)
        
        self.cancel_btn = QPushButton("انصراف")
        self.cancel_btn.setStyleSheet("background-color: #95a5a6; color: white; padding: 8px;")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addRow(btn_layout)

    def select_new_photos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب عکس‌های جدید", "", "Images (*.jpg *.jpeg *.png)")
        if files:
            for f in files:
                if f not in self.new_photos:
                    self.new_photos.append(f)
            self.lbl_photo_status.setText(f"{len(self.new_photos)} عکس آماده ذخیره")
            self.lbl_photo_status.setStyleSheet("color: #27ae60; font-weight: bold;")

    def start_saving_process(self):
        updated_data = {
            "name": self.name_input.text().strip(),
            "national_id": self.national_id_input.text().strip(),
            "phone_number": self.phone_input.text().strip()
        }

        self.save_btn.setEnabled(False)
        self.btn_add_photo.setEnabled(False)
        
        self.thread = EditWorkerThread(self.worker_id, self.original_name, updated_data, self.new_photos)
        self.thread.progress_signal.connect(self.lbl_loading.setText)
        self.thread.finished_signal.connect(self.on_process_finished)
        self.thread.start()

    def on_process_finished(self, success, message):
        self.save_btn.setEnabled(True)
        self.btn_add_photo.setEnabled(True)
        self.lbl_loading.setText("")
        
        if success:
            QMessageBox.information(self, "موفقیت", message)
            self.accept() # بستن فرم با موفقیت
        else:
            QMessageBox.critical(self, "خطا", message)

# -----------------------------------------------------------------
# کلاس اصلی صفحه لیست کارگران
# -----------------------------------------------------------------
class WorkersListPage(QWidget):
    # سیگنال برای انتقال کاربر به صفحه افزودن کارگر
    switch_to_add_worker = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("مدیریت و لیست کارگران")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)

        # ساخت جدول داده‌ها
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "آیدی", "نام و نام خانوادگی", "کد ملی", "تلفن همراه", "تاریخ ثبت", "عملیات سیستم"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # دادن فضای بیشتر به ستون عملیات به خاطر تعداد دکمه‌ها
        self.table.setColumnWidth(5, 320)
        self.table.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self.table)

        # --- بخش جدید: دکمه افزودن کارگر در پایین صفحه ---
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch() # هل دادن دکمه به سمت چپ
        
        add_btn = QPushButton("افزودن کارگر جدید +")
        add_btn.setStyleSheet("""
            background-color: #27ae60; 
            color: white; 
            font-weight: bold; 
            font-size: 14px; 
            padding: 10px 20px; 
            border-radius: 4px;
        """)
        add_btn.clicked.connect(self.switch_to_add_worker.emit)
        bottom_layout.addWidget(add_btn)
        layout.addLayout(bottom_layout)

        self.load_workers_data()


    def showEvent(self, event):
        """این متد هر زمان که کاربر وارد صفحه لیست کارگران شود، جدول را رفرش می‌کند"""
        super().showEvent(event)
        self.load_workers_data()


    def load_workers_data(self):
        self.thread = FetchWorkersThread()
        self.thread.workers_ready.connect(self.populate_table)
        self.thread.error_occurred.connect(self.show_error)
        self.thread.start()

    def populate_table(self, workers):
        self.table.setRowCount(0)
        for row_idx, worker in enumerate(workers):
            self.table.insertRow(row_idx)

            id_item = QTableWidgetItem(str(worker["id"]))
            id_item.setTextAlignment(Qt.AlignCenter)
            
            name_item = QTableWidgetItem(worker["name"])
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            
            nat_item = QTableWidgetItem(worker.get("national_id") or "---")
            nat_item.setTextAlignment(Qt.AlignCenter)
            
            phone_item = QTableWidgetItem(worker.get("phone_number") or "---")
            phone_item.setTextAlignment(Qt.AlignCenter)
            
            date_str = worker["created_at"].split("T")[0] if "T" in worker["created_at"] else worker["created_at"]
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, nat_item)
            self.table.setItem(row_idx, 3, phone_item)
            self.table.setItem(row_idx, 4, date_item)

            # ساخت نوار ابزار ۴ دکمه‌ای عملیات
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(5)

            # ۱. دکمه ویرایش (آبی)
            edit_btn = QPushButton("ویرایش")
            edit_btn.setStyleSheet("background-color: #3498db; color: white; font-size: 11px; padding: 4px 8px;")
            edit_btn.clicked.connect(lambda checked, w=worker: self.edit_worker(w))

            # ۲. دکمه لیست رخدادها (نارنجی)
            events_btn = QPushButton("رخدادها")
            events_btn.setStyleSheet("background-color: #e67e22; color: white; font-size: 11px; padding: 4px 8px;")
            events_btn.clicked.connect(lambda checked, w=worker: self.view_events(w))

            # ۳. دکمه اختصاص دوربین (بنفش - دمی برای آینده)
            cam_btn = QPushButton("دوربین")
            cam_btn.setStyleSheet("background-color: #9b59b6; color: white; font-size: 11px; padding: 4px 8px;")
            cam_btn.clicked.connect(lambda checked, w=worker: QMessageBox.information(self, "توسعه آینده", f"صفحه اختصاص دوربین به {w['name']} به زودی فعال می‌شود."))

            # ۴. دکمه حذف (قرمز)
            delete_btn = QPushButton("حذف")
            delete_btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 11px; padding: 4px 8px;")
            delete_btn.clicked.connect(lambda checked, w_id=worker["id"]: self.delete_worker(w_id))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(events_btn)
            actions_layout.addWidget(cam_btn)
            actions_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 5, actions_widget)

    def view_events(self, worker_data):
        dialog = WorkerEventsDialog(worker_data["id"], worker_data["name"], self)
        dialog.exec_()

    def edit_worker(self, worker_data):
        dialog = EditWorkerDialog(worker_data, self)
        if dialog.exec_() == QDialog.Accepted:
            # اگر دیالوگ با موفقیت بسته شد، جدول را رفرش کن تا تغییرات متنی روی جدول بنشیند
            self.load_workers_data()
            
    def delete_worker(self, worker_id):
        confirm = QMessageBox.question(
            self, "تایید حذف", "آیا از حذف کامل این کارگر اطمینان دارید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                response = requests.delete(f"http://localhost:8000/employees/{worker_id}")
                if response.status_code == 200:
                    QMessageBox.information(self, "موفقیت", "کارگر حذف شد.")
                    self.load_workers_data()
                else:
                    QMessageBox.critical(self, "خطا", "حذف انجام نشد.")
            except Exception as e:
                QMessageBox.critical(self, "خطا", f"خطا در ارتباط: {e}")

    def show_error(self, error_msg):
        QMessageBox.warning(self, "خطا", f"خطا در بارگذاری داده‌ها:\n{error_msg}")