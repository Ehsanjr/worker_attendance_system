import os
import shutil
import requests
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QMessageBox, QDialog, QLineEdit, QFormLayout, 
                             QLabel, QStackedWidget, QComboBox, QCheckBox, 
                             QTimeEdit, QGridLayout, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTime
from PyQt5.QtGui import QColor, QBrush, QFont

# تعیین مسیر پوشه کارگران برای ذخیره عکس‌های جدید
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

# -----------------------------------------------------------------
# Thread برای دریافت همزمان لیست کارگران و مپینگ دوربین‌ها
# -----------------------------------------------------------------
class FetchWorkersThread(QThread):
    workers_ready = pyqtSignal(list, dict) # لیست کارگران و دیکشنری مپینگ دوربین‌ها
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            # دریافت لیست دوربین‌ها برای نمایش نام به جای آیدی
            cam_res = requests.get("http://localhost:8000/cameras/")
            cam_map = {}
            if cam_res.status_code == 200:
                for c in cam_res.json():
                    cam_map[c["id"]] = c["name"]

            # دریافت لیست کارگران
            response = requests.get("http://localhost:8000/employees/")
            if response.status_code == 200:
                self.workers_ready.emit(response.json(), cam_map)
            else:
                self.error_occurred.emit("خطا در دریافت اطلاعات کارگران")
        except Exception as e:
            self.error_occurred.emit(str(e))

# -----------------------------------------------------------------
# پنجره پاپ‌آپ نمایش رخدادهای اختصاصی یک کارگر
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
        
        # صفحه ۲: پیام خالی
        self.empty_label = QLabel("هیچ رخدادی برای این کارگر در دیتابیس ثبت نشده است.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #7f8c8d;")
        self.stack.addWidget(self.empty_label)
        
        close_btn = QPushButton("بستن پنجره")
        close_btn.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.load_events(worker_id)

    def load_events(self, worker_id):
        try:
            camera_locations = {}
            try:
                cam_res = requests.get("http://localhost:8000/cameras/")
                if cam_res.status_code == 200:
                    for cam in cam_res.json():
                        camera_locations[cam.get("id")] = cam.get("location") or cam.get("name") or "نامشخص"
            except:
                pass 

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
                        
                        cam_id = ev.get("camera_id")
                        cam_loc = camera_locations.get(cam_id) or "لوکیشن نامشخص"
                        cam_item = QTableWidgetItem(str(cam_loc))
                        cam_item.setTextAlignment(Qt.AlignCenter)
                        
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
# Thread برای آپدیت اطلاعات (متنی + شیفت) و عکس‌های جدید در پس‌زمینه
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
            self.progress_signal.emit("در حال به‌روزرسانی اطلاعات متنی و شیفت...")
            update_res = requests.put(f"http://localhost:8000/employees/{self.worker_id}", json=self.updated_data)
            
            if update_res.status_code != 200:
                self.finished_signal.emit(False, "خطا در ویرایش اطلاعات متنی در سرور.")
                return

            if not self.new_photo_paths:
                self.finished_signal.emit(True, "اطلاعات و شیفت کارگر با موفقیت ویرایش شد.")
                return

            self.progress_signal.emit("در حال استخراج چهره‌های جدید...")
            folder_name = self.original_name.replace(" ", "_")
            worker_folder = WORKERS_DIR / folder_name
            worker_folder.mkdir(parents=True, exist_ok=True)

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
                        emb_payload = {"embedding": embedding_list, "image_path": str(dest_path)}
                        emb_res = requests.post(f"http://localhost:8000/employees/{self.worker_id}/embeddings", json=emb_payload)
                        if emb_res.status_code == 200: successful_embeddings += 1
                current_idx += 1

            self.finished_signal.emit(True, f"ویرایش موفق!\nتعداد {successful_embeddings} عکس جدید هم اضافه شد.")
        except Exception as e:
            self.finished_signal.emit(False, f"خطای سیستمی:\n{str(e)}")

# -----------------------------------------------------------------
# دیالوگ پاپ‌آپ پیشرفته برای ویرایش مشخصات + شیفت + عکس
# -----------------------------------------------------------------
class EditWorkerDialog(QDialog):
    def __init__(self, worker_data, cam_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ویرایش اطلاعات و شیفت کارگر")
        self.setFixedWidth(500)
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.worker_id = worker_data["id"]
        self.original_name = worker_data["name"]
        self.new_photos = []

        layout = QFormLayout(self)
        layout.setSpacing(10)

        # -- اطلاعات هویتی --
        self.name_input = QLineEdit(worker_data["name"])
        self.national_id_input = QLineEdit(worker_data.get("national_id") or "")
        self.phone_input = QLineEdit(worker_data.get("phone_number") or "")

        layout.addRow("نام کامل:", self.name_input)
        layout.addRow("کد ملی:", self.national_id_input)
        layout.addRow("تلفن همراه:", self.phone_input)

        # -- دوربین مجاز --
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("بدون محدودیت (همه دوربین‌ها)", None)
        for c_id, c_name in cam_map.items():
            self.combo_camera.addItem(f"{c_name} (ID: {c_id})", c_id)
        
        saved_cam_id = worker_data.get("camera_id")
        if saved_cam_id is not None:
            idx = self.combo_camera.findData(saved_cam_id)
            if idx >= 0: self.combo_camera.setCurrentIndex(idx)
            
        layout.addRow("دوربین مجاز:", self.combo_camera)

        # -- روزهای مجاز (اصلاح شده برای مقادیر None کارگران قدیمی) --
        allowed_days_str = worker_data.get("allowed_days") or "0,1,2,3,4,5,6"
        saved_days = allowed_days_str.split(",")
        
        self.days_checkboxes = {}
        days_mapping = [(5, "شنبه"), (6, "یک‌شنبه"), (0, "دوشنبه"), (1, "سه‌شنبه"), (2, "چهارشنبه"), (3, "پنج‌شنبه"), (4, "جمعه")]
        
        days_layout = QGridLayout()
        row, col = 0, 0
        for day_val, day_name in days_mapping:
            chk = QCheckBox(day_name)
            if str(day_val) in saved_days: chk.setChecked(True)
            self.days_checkboxes[day_val] = chk
            days_layout.addWidget(chk, row, col)
            col += 1
            if col > 3: col = 0; row += 1
                
        layout.addRow("روزهای مجاز:", days_layout)

        # -- ساعت شیفت (اصلاح شده برای مقادیر None کارگران قدیمی) --
        time_layout = QHBoxLayout()
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm")
        
        shift_start_str = worker_data.get("shift_start") or "00:00"
        h_s, m_s = map(int, shift_start_str.split(":"))
        self.time_start.setTime(QTime(h_s, m_s))
        
        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat("HH:mm")
        
        shift_end_str = worker_data.get("shift_end") or "23:59"
        h_e, m_e = map(int, shift_end_str.split(":"))
        self.time_end.setTime(QTime(h_e, m_e))

        time_layout.addWidget(QLabel("از:"))
        time_layout.addWidget(self.time_start)
        time_layout.addWidget(QLabel("تا:"))
        time_layout.addWidget(self.time_end)
        layout.addRow("ساعت شیفت:", time_layout)

        # -- افزودن عکس جدید --
        photo_layout = QHBoxLayout()
        self.btn_add_photo = QPushButton("➕ افزودن عکس جدید")
        self.btn_add_photo.setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        self.btn_add_photo.clicked.connect(self.select_new_photos)
        
        self.lbl_photo_status = QLabel("بدون عکس جدید")
        photo_layout.addWidget(self.btn_add_photo)
        photo_layout.addWidget(self.lbl_photo_status)
        layout.addRow("تکمیل چهره:", photo_layout)

        self.lbl_loading = QLabel("")
        self.lbl_loading.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 12px;")
        layout.addRow(self.lbl_loading)

        # -- دکمه‌ها --
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
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب عکس", "", "Images (*.jpg *.png)")
        if files:
            for f in files:
                if f not in self.new_photos: self.new_photos.append(f)
            self.lbl_photo_status.setText(f"{len(self.new_photos)} عکس اضافه شد")

    def start_saving_process(self):
        selected_days = [str(val) for val, chk in self.days_checkboxes.items() if chk.isChecked()]
        updated_data = {
            "name": self.name_input.text().strip(),
            "national_id": self.national_id_input.text().strip(),
            "phone_number": self.phone_input.text().strip(),
            "camera_id": self.combo_camera.currentData(),
            "allowed_days": ",".join(selected_days),
            "shift_start": self.time_start.time().toString("HH:mm"),
            "shift_end": self.time_end.time().toString("HH:mm")
        }

        self.save_btn.setEnabled(False)
        self.thread = EditWorkerThread(self.worker_id, self.original_name, updated_data, self.new_photos)
        self.thread.progress_signal.connect(self.lbl_loading.setText)
        self.thread.finished_signal.connect(self.on_process_finished)
        self.thread.start()

    def on_process_finished(self, success, message):
        self.save_btn.setEnabled(True)
        self.lbl_loading.setText("")
        if success:
            QMessageBox.information(self, "موفقیت", message)
            self.accept()
        else:
            QMessageBox.critical(self, "خطا", message)

# -----------------------------------------------------------------
# کلاس اصلی صفحه لیست کارگران
# -----------------------------------------------------------------
class WorkersListPage(QWidget):
    switch_to_add_worker = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.cam_map = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("مدیریت و لیست کارگران")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)

        # جدول کارگران با هدرهای جدید
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "آیدی", "نام و نام خانوادگی", "ارتباطات", "دوربین / شیفت مجاز", "تاریخ ثبت", "عملیات سیستم"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(5, 230)
        self.table.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
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

    def showEvent(self, event):
        """هر زمان کاربر وارد صفحه شود جدول رفرش می‌شود"""
        super().showEvent(event)
        self.load_workers_data()

    def load_workers_data(self):
        self.thread = FetchWorkersThread()
        self.thread.workers_ready.connect(self.populate_table)
        self.thread.error_occurred.connect(lambda err: QMessageBox.warning(self, "خطا", err))
        self.thread.start()

    def populate_table(self, workers, cam_map):
        self.cam_map = cam_map
        self.table.setRowCount(0)
        for row_idx, worker in enumerate(workers):
            self.table.insertRow(row_idx)

            id_item = QTableWidgetItem(str(worker["id"]))
            id_item.setTextAlignment(Qt.AlignCenter)
            
            name_item = QTableWidgetItem(worker["name"])
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            
            contact_str = f"ملی: {worker.get('national_id') or '---'}\nتماس: {worker.get('phone_number') or '---'}"
            contact_item = QTableWidgetItem(contact_str)
            contact_item.setTextAlignment(Qt.AlignCenter)
            
            # --- نمایش اطلاعات ترکیبی شیفت و دوربین ---
            c_id = worker.get("camera_id")
            cam_name = cam_map.get(c_id, f"آیدی {c_id}") if c_id is not None else "همه دوربین‌ها"
            s_start = worker.get("shift_start", "00:00")
            s_end = worker.get("shift_end", "23:59")
            
            shift_info = f"دوربین: {cam_name}\nساعت: {s_start} تا {s_end}"
            shift_item = QTableWidgetItem(shift_info)
            shift_item.setTextAlignment(Qt.AlignCenter)
            shift_item.setForeground(QBrush(QColor("#2980b9")))
            
            date_str = worker["created_at"].split("T")[0] if "T" in worker["created_at"] else worker["created_at"]
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, contact_item)
            self.table.setItem(row_idx, 3, shift_item)
            self.table.setItem(row_idx, 4, date_item)
            self.table.setRowHeight(row_idx, 50) # افزایش ارتفاع سطر برای جا شدن متون دوخطی

            # نوار ابزار ۳ دکمه‌ای عملیات (دکمه دوربین جداگانه حذف شد چون داخل ویرایش رفت)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(5)

            edit_btn = QPushButton("ویرایش")
            edit_btn.setStyleSheet("background-color: #3498db; color: white; font-size: 11px; padding: 4px 8px;")
            edit_btn.clicked.connect(lambda checked, w=worker: self.edit_worker(w))

            events_btn = QPushButton("رخدادها")
            events_btn.setStyleSheet("background-color: #e67e22; color: white; font-size: 11px; padding: 4px 8px;")
            events_btn.clicked.connect(lambda checked, w=worker: self.view_events(w))

            delete_btn = QPushButton("حذف")
            delete_btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 11px; padding: 4px 8px;")
            delete_btn.clicked.connect(lambda checked, w_id=worker["id"]: self.delete_worker(w_id))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(events_btn)
            actions_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 5, actions_widget)

    def edit_worker(self, worker_data):
        dialog = EditWorkerDialog(worker_data, self.cam_map, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_workers_data()

    def view_events(self, worker_data):
        dialog = WorkerEventsDialog(worker_data["id"], worker_data["name"], self)
        dialog.exec_()

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