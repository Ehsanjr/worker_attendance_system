import os
import shutil
import requests
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
                             QComboBox, QCheckBox, QGridLayout, QGroupBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

# -----------------------------------------------------------------
# 1. کلاس ویجت تصویر بندانگشتی (Thumbnail)
# -----------------------------------------------------------------
class ThumbnailWidget(QWidget):
    def __init__(self, img_path, remove_callback, parent=None):
        super().__init__(parent)
        self.img_path = img_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        self.img_label = QLabel()
        self.img_label.setFixedSize(80, 80)
        self.img_label.setStyleSheet("border: 1px solid #bdc3c7; border-radius: 4px;")
        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            self.img_label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            self.img_label.setAlignment(Qt.AlignCenter)
        
        self.del_btn = QPushButton("حذف ❌")
        self.del_btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 10px; padding: 2px;")
        self.del_btn.clicked.connect(lambda: remove_callback(self.img_path, self))

        layout.addWidget(self.img_label)
        layout.addWidget(self.del_btn)

# -----------------------------------------------------------------
# 2. پاپ‌آپ افزودن شیفت موقت (اصلاح شده با منوی کشویی کاربرپسند)
# -----------------------------------------------------------------
class AddShiftDialog(QDialog):
    def __init__(self, cam_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تعریف شیفت و دوربین جدید")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.RightToLeft)
        self.shift_data = None
        
        layout = QFormLayout(self)
        
        # دوربین
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("همه دوربین‌ها", None)
        for c_id, c_name in cam_map.items():
            self.combo_camera.addItem(c_name, c_id)
        layout.addRow("دوربین مجاز:", self.combo_camera)

        # روزها
        self.days_checkboxes = {}
        days_mapping = [(5, "شنبه"), (6, "یک‌شنبه"), (0, "دوشنبه"), (1, "سه‌شنبه"), (2, "چهارشنبه"), (3, "پنج‌شنبه"), (4, "جمعه")]
        days_layout = QGridLayout()
        row, col = 0, 0
        for day_val, day_name in days_mapping:
            chk = QCheckBox(day_name)
            chk.setChecked(True) if day_val != 4 else chk.setChecked(False)
            self.days_checkboxes[day_val] = chk
            days_layout.addWidget(chk, row, col)
            col += 1
            if col > 3: col = 0; row += 1
        layout.addRow("روزهای مجاز:", days_layout)

        # 🔴 سیستم جدید انتخاب ساعت (Drop-down)
        time_layout = QHBoxLayout()
        
        # ساعت شروع
        self.start_h_cb = QComboBox()
        self.start_h_cb.addItems([f"{h:02d}" for h in range(24)])
        self.start_h_cb.setCurrentText("08") # پیش‌فرض ۸ صبح
        
        self.start_m_cb = QComboBox()
        self.start_m_cb.addItems([f"{m:02d}" for m in range(60)])
        self.start_m_cb.setCurrentText("00")

        # ساعت پایان
        self.end_h_cb = QComboBox()
        self.end_h_cb.addItems([f"{h:02d}" for h in range(24)])
        self.end_h_cb.setCurrentText("17") # پیش‌فرض ۵ عصر
        
        self.end_m_cb = QComboBox()
        self.end_m_cb.addItems([f"{m:02d}" for m in range(60)])
        self.end_m_cb.setCurrentText("00")

        time_layout.addWidget(QLabel("از:"))
        time_layout.addWidget(self.start_h_cb)
        time_layout.addWidget(QLabel(":"))
        time_layout.addWidget(self.start_m_cb)
        time_layout.addSpacing(15)
        time_layout.addWidget(QLabel("تا:"))
        time_layout.addWidget(self.end_h_cb)
        time_layout.addWidget(QLabel(":"))
        time_layout.addWidget(self.end_m_cb)
        
        layout.addRow("ساعت شیفت:", time_layout)

        # دکمه‌ها
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("تایید و افزودن به لیست")
        save_btn.setStyleSheet("background-color: #3498db; color: white; padding: 6px; font-weight: bold;")
        save_btn.clicked.connect(self.submit)
        btn_layout.addWidget(save_btn)
        layout.addRow(btn_layout)

    def submit(self):
        selected_days = [str(val) for val, chk in self.days_checkboxes.items() if chk.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "خطا", "حداقل یک روز کاری باید انتخاب شود.")
            return

        start_time_str = f"{self.start_h_cb.currentText()}:{self.start_m_cb.currentText()}"
        end_time_str = f"{self.end_h_cb.currentText()}:{self.end_m_cb.currentText()}"

        self.shift_data = {
            "camera_id": self.combo_camera.currentData(),
            "camera_name": self.combo_camera.currentText(),
            "allowed_days": ",".join(selected_days),
            "shift_start": start_time_str,
            "shift_end": end_time_str
        }
        self.accept()

# -----------------------------------------------------------------
# 3. Thread ثبت‌نام نهایی 
# -----------------------------------------------------------------
class AddWorkerThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str)

    def __init__(self, payload, photo_paths):
        super().__init__()
        self.payload = payload
        self.photo_paths = photo_paths

    def run(self):
        try:
            self.progress_signal.emit("در حال ثبت اطلاعات متنی و شیفت‌ها...")
            response = requests.post("http://localhost:8000/employees/", json=self.payload)
            if response.status_code != 200:
                self.finished_signal.emit(False, "خطا: سرور بک‌اند اطلاعات را قبول نکرد.")
                return

            worker_id = response.json().get("id")
            folder_name = self.payload["name"].replace(" ", "_")

            worker_folder = WORKERS_DIR / folder_name
            worker_folder.mkdir(parents=True, exist_ok=True)

            self.progress_signal.emit("در حال پردازش چهره‌ها در هوش مصنوعی...")
            app = FaceAnalysis(name="buffalo_l")
            app.prepare(ctx_id=0)

            successful_embeddings = 0
            for idx, src_path in enumerate(self.photo_paths):
                suffix = Path(src_path).suffix.lower() or ".jpg"
                dest_path = worker_folder / f"face{idx + 1}{suffix}"
                shutil.copy(src_path, dest_path)
                
                img = cv2.imread(str(dest_path))
                if img is None: continue

                faces = app.get(img)
                if len(faces) == 0: continue

                emb_payload = {"embedding": faces[0].embedding.tolist(), "image_path": str(dest_path)}
                emb_res = requests.post(f"http://localhost:8000/employees/{worker_id}/embeddings", json=emb_payload)
                if emb_res.status_code == 200: successful_embeddings += 1

            self.finished_signal.emit(True, f"کارگر با موفقیت ثبت شد!\n{len(self.payload['shifts'])} شیفت و {successful_embeddings} چهره ذخیره گردید.")

        except Exception as e:
            self.finished_signal.emit(False, f"خطای غیرمنتظره:\n{str(e)}")

# -----------------------------------------------------------------
# 4. صفحه اصلی UI
# -----------------------------------------------------------------
class AddWorkerPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.selected_photos = []
        self.shifts_list = []
        self.cam_map = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 20, 40, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("ثبت مشخصات و افزودن چهره کارگر جدید")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title_label)

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

        shift_group = QGroupBox("برنامه‌های زمانی و شیفت‌های کارگر")
        shift_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2980b9; border: 1px solid #bdc3c7; padding: 10px; margin-top: 10px; }")
        shift_layout = QVBoxLayout(shift_group)

        self.btn_add_shift = QPushButton("➕ افزودن شیفت و دوربین جدید")
        self.btn_add_shift.setStyleSheet("background-color: #8e44ad; color: white; padding: 6px; font-weight: bold; max-width: 200px;")
        self.btn_add_shift.clicked.connect(self.open_add_shift_dialog)
        shift_layout.addWidget(self.btn_add_shift)

        self.shifts_table = QTableWidget()
        self.shifts_table.setColumnCount(4)
        self.shifts_table.setHorizontalHeaderLabels(["دوربین مجاز", "تعداد روزها", "ساعت کاری", "عملیات"])
        self.shifts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.shifts_table.setFixedHeight(150)
        shift_layout.addWidget(self.shifts_table)
        main_layout.addWidget(shift_group)

        photo_group = QGroupBox("انتخاب چهره‌ها")
        photo_group.setStyleSheet("QGroupBox { font-weight: bold; color: #16a085; border: 1px solid #bdc3c7; padding: 10px; margin-top: 5px; }")
        photo_layout = QVBoxLayout(photo_group)
        
        self.btn_select_photos = QPushButton("📸 انتخاب عکس از سیستم...")
        self.btn_select_photos.setStyleSheet("background-color: #16a085; color: white; padding: 8px; font-weight: bold; max-width: 200px;")
        self.btn_select_photos.clicked.connect(self.choose_photos_dialog)
        photo_layout.addWidget(self.btn_select_photos)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFixedHeight(120)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.gallery_layout = QHBoxLayout(self.scroll_widget)
        self.gallery_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.scroll_widget)
        photo_layout.addWidget(self.scroll_area)
        
        main_layout.addWidget(photo_group)

        self.lbl_loading = QLabel("")
        self.lbl_loading.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 13px;")
        self.lbl_loading.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_loading)

        self.btn_submit = QPushButton("💾 ذخیره کارگر و شیفت‌ها")
        self.btn_submit.setStyleSheet("background-color: #2ecc71; color: white; font-size: 15px; font-weight: bold; padding: 12px; border-radius: 5px;")
        self.btn_submit.clicked.connect(self.submit_form_data)
        main_layout.addWidget(self.btn_submit)

        self.load_active_cameras()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_active_cameras()

    def load_active_cameras(self):
        try:
            res = requests.get("http://localhost:8000/cameras/")
            if res.status_code == 200:
                self.cam_map = {c["id"]: c["name"] for c in res.json() if c.get("is_active", True)}
        except: pass

    def open_add_shift_dialog(self):
        dialog = AddShiftDialog(self.cam_map, self)
        if dialog.exec_() == QDialog.Accepted:
            self.shifts_list.append(dialog.shift_data)
            self.refresh_shifts_table()

    def refresh_shifts_table(self):
        self.shifts_table.setRowCount(0)
        for idx, shift in enumerate(self.shifts_list):
            self.shifts_table.insertRow(idx)
            
            cam_item = QTableWidgetItem(shift["camera_name"])
            cam_item.setTextAlignment(Qt.AlignCenter)
            
            days_count = len(shift["allowed_days"].split(","))
            days_item = QTableWidgetItem(f"{days_count} روز در هفته")
            days_item.setTextAlignment(Qt.AlignCenter)
            
            time_item = QTableWidgetItem(f"{shift['shift_start']} تا {shift['shift_end']}")
            time_item.setTextAlignment(Qt.AlignCenter)
            
            del_btn = QPushButton("حذف شیفت 🗑")
            del_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 2px;")
            del_btn.clicked.connect(lambda _, i=idx: self.remove_shift(i))

            self.shifts_table.setItem(idx, 0, cam_item)
            self.shifts_table.setItem(idx, 1, days_item)
            self.shifts_table.setItem(idx, 2, time_item)
            self.shifts_table.setCellWidget(idx, 3, del_btn)

    def remove_shift(self, index):
        self.shifts_list.pop(index)
        self.refresh_shifts_table()

    def choose_photos_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب عکس", "", "Images (*.jpg *.png)")
        if files:
            for f in files:
                if f not in self.selected_photos:
                    self.selected_photos.append(f)
                    thumb = ThumbnailWidget(f, self.remove_photo_from_gallery)
                    self.gallery_layout.addWidget(thumb)

    def remove_photo_from_gallery(self, img_path, widget):
        self.selected_photos.remove(img_path)
        self.gallery_layout.removeWidget(widget)
        widget.deleteLater()

    def clear_all(self):
        self.input_first_name.clear()
        self.input_last_name.clear()
        self.input_national_id.clear()
        self.input_phone.clear()
        self.shifts_list.clear()
        self.refresh_shifts_table()
        self.selected_photos.clear()
        for i in reversed(range(self.gallery_layout.count())): 
            self.gallery_layout.itemAt(i).widget().deleteLater()

    def submit_form_data(self):
        first_name = self.input_first_name.text().strip()
        last_name = self.input_last_name.text().strip()

        if not first_name or not last_name:
            QMessageBox.warning(self, "خطا", "لطفاً نام و نام خانوادگی را وارد کنید.")
            return
        if not self.selected_photos:
            QMessageBox.warning(self, "خطا", "انتخاب حداقل یک عکس الزامی است.")
            return
        if not self.shifts_list:
            reply = QMessageBox.question(self, "هشدار شیفت", "هیچ شیفتی تعریف نکرده‌اید. کارگر اجازه ورود نخواهد داشت! ادامه می‌دهید؟", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return

        payload = {
            "name": f"{first_name} {last_name}",
            "national_id": self.input_national_id.text().strip(),
            "phone_number": self.input_phone.text().strip(),
            "shifts": self.shifts_list 
        }

        self.btn_submit.setEnabled(False)
        self.thread = AddWorkerThread(payload, self.selected_photos)
        self.thread.progress_signal.connect(self.lbl_loading.setText)
        self.thread.finished_signal.connect(self.on_registration_finished)
        self.thread.start()

    def on_registration_finished(self, success, message):
        self.btn_submit.setEnabled(True)
        self.lbl_loading.setText("")
        if success:
            QMessageBox.information(self, "موفق", message)
            self.clear_all()
        else:
            QMessageBox.critical(self, "خطا", message)