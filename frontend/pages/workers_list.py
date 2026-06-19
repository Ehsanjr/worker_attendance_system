import os
import shutil
import time
import requests
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QMessageBox, QDialog, QLineEdit, QFormLayout, 
                             QLabel, QComboBox, QCheckBox, QGridLayout, 
                             QFileDialog, QGroupBox, QScrollArea)
# 🔴 اضافه شدن QSettings
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtGui import QColor, QBrush, QFont, QPixmap

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

def validate_shift_logic(new_shift, existing_shifts, exclude_id=None, cam_map=None):
    warnings = []
    if new_shift["shift_start"] == new_shift["shift_end"]:
        warnings.append("ساعت شروع و پایان یکسان است (شیفت ۰ دقیقه‌ای ایجاد کرده‌اید!).")

    def t2m(t_str):
        h, m = map(int, t_str.split(":"))
        return h * 60 + m

    new_days = set(new_shift["allowed_days"].split(","))
    ns, ne = t2m(new_shift["shift_start"]), t2m(new_shift["shift_end"])
    new_intervals = [(ns, ne)] if ns <= ne else [(ns, 24*60), (0, ne)]

    for shift in existing_shifts:
        if exclude_id is not None and shift.get("id") == exclude_id: continue
        exist_days = set(shift["allowed_days"].split(","))
        common_days = new_days.intersection(exist_days)
        if not common_days: continue
            
        es, ee = t2m(shift["shift_start"]), t2m(shift["shift_end"])
        exist_intervals = [(es, ee)] if es <= ee else [(es, 24*60), (0, ee)]
        
        overlap = False
        for n_start, n_end in new_intervals:
            for e_start, e_end in exist_intervals:
                if max(n_start, e_start) < min(n_end, e_end):
                    overlap = True
                    break
            if overlap: break
            
        if overlap:
            c_id = shift.get("camera_id")
            c_name = cam_map.get(c_id, "دوربین نامشخص") if cam_map and c_id else "همه دوربین‌ها"
            warnings.append(f"تداخل زمانی در روزهای مشترک با شیفت ({shift['shift_start']} تا {shift['shift_end']} - {c_name}).")
    return warnings

class FetchWorkersThread(QThread):
    workers_ready = pyqtSignal(list, dict) 
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            cam_res = requests.get("http://localhost:8000/cameras/")
            cam_map = {c["id"]: c["name"] for c in cam_res.json()} if cam_res.status_code == 200 else {}
            response = requests.get("http://localhost:8000/employees/")
            if response.status_code == 200:
                self.workers_ready.emit(response.json(), cam_map)
            else:
                self.error_occurred.emit("خطا در دریافت اطلاعات")
        except Exception as e:
            self.error_occurred.emit(str(e))

class EditWorkerTextThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    def __init__(self, worker_id, updated_data):
        super().__init__()
        self.worker_id = worker_id
        self.updated_data = updated_data
    def run(self):
        try:
            res = requests.put(f"http://localhost:8000/employees/{self.worker_id}", json=self.updated_data)
            if res.status_code == 200: self.finished_signal.emit(True, "OK")
            else: self.finished_signal.emit(False, "Error")
        except Exception as e: self.finished_signal.emit(False, str(e))

class ProcessAndAddPhotoThread(QThread):
    finished_signal = pyqtSignal(bool, str, list)
    progress_signal = pyqtSignal(str)

    def __init__(self, worker_id, worker_name, photo_paths):
        super().__init__()
        self.worker_id = worker_id
        self.worker_name = worker_name
        self.photo_paths = photo_paths

    def run(self):
        try:
            self.progress_signal.emit("در حال بررسی چهره در هوش مصنوعی...")
            folder_name = self.worker_name.replace(" ", "_")
            worker_folder = WORKERS_DIR / folder_name
            worker_folder.mkdir(parents=True, exist_ok=True)

            app = FaceAnalysis(name="buffalo_l")
            app.prepare(ctx_id=0)

            added_data = []
            for src_path in self.photo_paths:
                suffix = Path(src_path).suffix.lower() or ".jpg"
                dest_path = worker_folder / f"face_{int(time.time() * 1000)}{suffix}"
                shutil.copy(src_path, dest_path)

                img = cv2.imread(str(dest_path))
                if img is None: continue
                faces = app.get(img)
                if len(faces) == 0:
                    os.remove(dest_path) 
                    continue

                emb_payload = {"embedding": faces[0].embedding.tolist(), "image_path": str(dest_path)}
                emb_res = requests.post(f"http://localhost:8000/employees/{self.worker_id}/embeddings", json=emb_payload)
                if emb_res.status_code == 200:
                    new_id = emb_res.json().get("embedding_id")
                    added_data.append({"id": new_id, "image_path": str(dest_path)})

            if added_data: self.finished_signal.emit(True, "موفق", added_data)
            else: self.finished_signal.emit(False, "هیچ چهره‌ای یافت نشد!", [])
        except Exception as e: self.finished_signal.emit(False, str(e), [])

class ThumbnailWidget(QWidget):
    def __init__(self, emb_id, img_path, remove_callback, parent=None):
        super().__init__(parent)
        self.emb_id = emb_id
        self.img_path = img_path
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        self.img_label = QLabel()
        self.img_label.setFixedSize(80, 80)
        self.img_label.setStyleSheet("border: 1px solid #bdc3c7; border-radius: 4px;")
        pixmap = QPixmap(img_path)
        if not pixmap.isNull(): self.img_label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else: self.img_label.setText("نامعتبر")
        
        self.del_btn = QPushButton("حذف ❌")
        self.del_btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 10px; padding: 2px;")
        self.del_btn.clicked.connect(lambda: remove_callback(self.emb_id, self.img_path, self))
        layout.addWidget(self.img_label)
        layout.addWidget(self.del_btn)

class EditWorkerBasicDialog(QDialog):
    def __init__(self, worker_data, parent=None):
        super().__init__(parent)
        self.settings = QSettings("SmartVision", "AttendanceSystem")
        self.t_single = self.settings.value("term_singular", "کارگر")
        
        self.setWindowTitle(f"ویرایش مشخصات و گالری - {worker_data['name']}")
        self.setFixedWidth(450)
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.worker_id = worker_data["id"]
        self.worker_name = worker_data["name"]

        main_layout = QVBoxLayout(self)

        form_group = QGroupBox("ویرایش اطلاعات متنی")
        form_layout = QFormLayout(form_group)
        self.name_input = QLineEdit(worker_data["name"])
        self.national_id_input = QLineEdit(worker_data.get("national_id") or "")
        self.phone_input = QLineEdit(worker_data.get("phone_number") or "")

        form_layout.addRow("نام کامل:", self.name_input)
        form_layout.addRow("کد ملی:", self.national_id_input)
        form_layout.addRow("تلفن همراه:", self.phone_input)
        main_layout.addWidget(form_group)

        photo_group = QGroupBox("مدیریت چهره‌های شناسایی (هوش مصنوعی)")
        photo_layout = QVBoxLayout(photo_group)
        
        top_photo_layout = QHBoxLayout()
        self.btn_add_photo = QPushButton("➕ افزودن عکس جدید...")
        self.btn_add_photo.setStyleSheet("background-color: #16a085; color: white; padding: 6px; font-weight: bold;")
        self.btn_add_photo.clicked.connect(self.choose_and_add_photos)
        top_photo_layout.addWidget(self.btn_add_photo)
        
        self.lbl_photo_status = QLabel("")
        self.lbl_photo_status.setStyleSheet("color: #e67e22; font-size: 11px;")
        top_photo_layout.addWidget(self.lbl_photo_status)
        top_photo_layout.addStretch()
        photo_layout.addLayout(top_photo_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFixedHeight(130)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.gallery_layout = QHBoxLayout(self.scroll_widget)
        self.gallery_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.scroll_widget)
        photo_layout.addWidget(self.scroll_area)
        main_layout.addWidget(photo_group)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 ذخیره تغییرات هویتی")
        self.save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")
        self.save_btn.clicked.connect(self.submit_text_changes)
        
        self.cancel_btn = QPushButton("انصراف")
        self.cancel_btn.setStyleSheet("background-color: #95a5a6; color: white; padding: 10px; font-weight: bold;")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

        self.load_existing_photos()

    def load_existing_photos(self):
        try:
            res = requests.get(f"http://localhost:8000/employees/{self.worker_id}/embeddings")
            if res.status_code == 200:
                for emb in res.json(): self.add_thumbnail_to_gallery(emb["id"], emb["image_path"])
        except Exception as e: print(e)

    def add_thumbnail_to_gallery(self, emb_id, img_path):
        thumb = ThumbnailWidget(emb_id, img_path, self.delete_photo, self)
        self.gallery_layout.addWidget(thumb)

    def choose_and_add_photos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب عکس", "", "Images (*.jpg *.png)")
        if not files: return
        self.btn_add_photo.setEnabled(False)
        self.photo_thread = ProcessAndAddPhotoThread(self.worker_id, self.worker_name, files)
        self.photo_thread.progress_signal.connect(self.lbl_photo_status.setText)
        self.photo_thread.finished_signal.connect(self.on_photos_processed)
        self.photo_thread.start()

    def on_photos_processed(self, success, msg, added_data):
        self.btn_add_photo.setEnabled(True)
        self.lbl_photo_status.setText("")
        if success:
            for item in added_data: self.add_thumbnail_to_gallery(item["id"], item["image_path"])
        else: QMessageBox.warning(self, "خطا", msg)

    def delete_photo(self, emb_id, img_path, widget):
        reply = QMessageBox.question(self, 'حذف عکس', 'آیا از حذف این چهره اطمینان دارید؟', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return
        try:
            res = requests.delete(f"http://localhost:8000/employees/embeddings/{emb_id}")
            if res.status_code == 200:
                if os.path.exists(img_path): os.remove(img_path)
                self.gallery_layout.removeWidget(widget)
                widget.deleteLater()
        except Exception as e: QMessageBox.critical(self, "خطا", str(e))

    def submit_text_changes(self):
        payload = {
            "name": self.name_input.text().strip(),
            "national_id": self.national_id_input.text().strip(),
            "phone_number": self.phone_input.text().strip()
        }
        self.save_btn.setEnabled(False)
        self.text_thread = EditWorkerTextThread(self.worker_id, payload)
        self.text_thread.finished_signal.connect(self.on_text_finished)
        self.text_thread.start()

    def on_text_finished(self, success, msg):
        self.save_btn.setEnabled(True)
        if success: 
            # 🔴 نمایش پیام موفقیت‌آمیز به صورت کاملاً ساده بر اساس فیدبک شما
            QMessageBox.information(self, "موفقیت", "تغییرات با موفقیت ذخیره شد.")
            self.accept()
        else: QMessageBox.critical(self, "خطا", "خطا در برقراری ارتباط")

class EditShiftDialog(QDialog):
    def __init__(self, shift_data, cam_map, existing_shifts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ویرایش شیفت")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.RightToLeft)
        self.shift_data = shift_data
        self.cam_map = cam_map
        self.existing_shifts = existing_shifts

        layout = QFormLayout(self)
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("همه دوربین‌ها", None)
        for c_id, c_name in self.cam_map.items(): self.combo_camera.addItem(c_name, c_id)
        saved_cam_id = shift_data.get("camera_id")
        if saved_cam_id is not None:
            idx = self.combo_camera.findData(saved_cam_id)
            if idx >= 0: self.combo_camera.setCurrentIndex(idx)
        layout.addRow("دوربین:", self.combo_camera)

        saved_days = shift_data.get("allowed_days", "").split(",")
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
        layout.addRow("روزها:", days_layout)

        time_layout = QHBoxLayout()
        self.start_h_cb = QComboBox()
        self.start_h_cb.addItems([f"{h:02d}" for h in range(24)])
        self.start_m_cb = QComboBox()
        self.start_m_cb.addItems([f"{m:02d}" for m in range(60)])
        s_h, s_m = shift_data.get("shift_start", "08:00").split(":")
        self.start_h_cb.setCurrentText(s_h)
        self.start_m_cb.setCurrentText(s_m)

        self.end_h_cb = QComboBox()
        self.end_h_cb.addItems([f"{h:02d}" for h in range(24)])
        self.end_m_cb = QComboBox()
        self.end_m_cb.addItems([f"{m:02d}" for m in range(60)])
        e_h, e_m = shift_data.get("shift_end", "17:00").split(":")
        self.end_h_cb.setCurrentText(e_h)
        self.end_m_cb.setCurrentText(e_m)

        time_layout.addWidget(QLabel("از:"))
        time_layout.addWidget(self.start_h_cb)
        time_layout.addWidget(QLabel(":"))
        time_layout.addWidget(self.start_m_cb)
        time_layout.addSpacing(15)
        time_layout.addWidget(QLabel("تا:"))
        time_layout.addWidget(self.end_h_cb)
        time_layout.addWidget(QLabel(":"))
        time_layout.addWidget(self.end_m_cb)
        layout.addRow("ساعت:", time_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 ذخیره تغییرات شیفت")
        save_btn.setStyleSheet("background-color: #2ecc71; color: white; padding: 6px; font-weight: bold;")
        save_btn.clicked.connect(self.submit)
        cancel_btn = QPushButton("انصراف")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def submit(self):
        selected_days = [str(val) for val, chk in self.days_checkboxes.items() if chk.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "خطا", "لطفاً حداقل یک روز را انتخاب کنید.")
            return
        payload = {
            "camera_id": self.combo_camera.currentData(),
            "allowed_days": ",".join(selected_days),
            "shift_start": f"{self.start_h_cb.currentText()}:{self.start_m_cb.currentText()}",
            "shift_end": f"{self.end_h_cb.currentText()}:{self.end_m_cb.currentText()}"
        }
        warnings = validate_shift_logic(payload, self.existing_shifts, exclude_id=self.shift_data["id"], cam_map=self.cam_map)
        if warnings:
            msg = "⚠️ هشدارهای منطقی زیر یافت شد:\n\n" + "\n".join([f"❌ {w}" for w in warnings]) + "\n\nآیا با این حال می‌خواهید ویرایش را ذخیره کنید؟"
            reply = QMessageBox.warning(self, "تداخل یافت شد", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        try:
            res = requests.put(f"http://localhost:8000/employees/shifts/{self.shift_data['id']}", json=payload)
            if res.status_code == 200: self.accept()
        except Exception as e: QMessageBox.critical(self, "خطا", str(e))

class ManageShiftsDialog(QDialog):
    def __init__(self, worker_id, worker_name, cam_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"مدیریت شیفت‌ها - {worker_name}")
        self.setFixedSize(550, 500)
        self.setLayoutDirection(Qt.RightToLeft)
        self.worker_id = worker_id
        self.cam_map = cam_map
        self.current_shifts = []

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["دوربین", "روزها", "ساعت", "عملیات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        add_title = QLabel("--- ✨ افزودن شیفت جدید ✨ ---")
        add_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px; margin-top: 10px;")
        add_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(add_title)

        add_group = QFormLayout()
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("همه دوربین‌ها", None)
        for c_id, c_name in self.cam_map.items(): self.combo_camera.addItem(c_name, c_id)
        add_group.addRow("دوربین:", self.combo_camera)

        self.days_checkboxes = {}
        days_mapping = [(5, "شنبه"), (6, "یک‌شنبه"), (0, "دوشنبه"), (1, "سه‌شنبه"), (2, "چهارشنبه"), (3, "پنج‌شنبه"), (4, "جمعه")]
        days_layout = QGridLayout()
        row, col = 0, 0
        for day_val, day_name in days_mapping:
            chk = QCheckBox(day_name)
            self.days_checkboxes[day_val] = chk
            days_layout.addWidget(chk, row, col)
            col += 1
            if col > 3: col = 0; row += 1
        add_group.addRow("روزها:", days_layout)

        time_layout = QHBoxLayout()
        self.start_h_cb = QComboBox()
        self.start_h_cb.addItems([f"{h:02d}" for h in range(24)])
        self.start_h_cb.setCurrentText("08")
        self.start_m_cb = QComboBox()
        self.start_m_cb.addItems([f"{m:02d}" for m in range(60)])
        self.start_m_cb.setCurrentText("00")

        self.end_h_cb = QComboBox()
        self.end_h_cb.addItems([f"{h:02d}" for h in range(24)])
        self.end_h_cb.setCurrentText("17")
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
        add_group.addRow("ساعت:", time_layout)

        btn_add = QPushButton("➕ ثبت شیفت جدید در دیتابیس")
        btn_add.setStyleSheet("background-color: #8e44ad; color: white; padding: 8px; font-weight: bold;")
        btn_add.clicked.connect(self.add_new_shift)
        add_group.addRow(btn_add)
        layout.addLayout(add_group)
        self.load_shifts()

    def load_shifts(self):
        try:
            res = requests.get(f"http://localhost:8000/employees/{self.worker_id}")
            if res.status_code == 200:
                shifts = [s for s in res.json().get("shifts", []) if not s.get("is_deleted", False)]
                self.current_shifts = shifts
                self.populate_table(shifts)
        except Exception as e: print(e)

    def populate_table(self, shifts):
        self.table.setRowCount(0)
        for idx, shift in enumerate(shifts):
            self.table.insertRow(idx)
            c_id = shift.get("camera_id")
            c_name = self.cam_map.get(c_id, "همه دوربین‌ها") if c_id is not None else "همه دوربین‌ها"
            cam_item = QTableWidgetItem(c_name)
            cam_item.setTextAlignment(Qt.AlignCenter)
            
            days_count = len(shift.get("allowed_days", "").split(","))
            days_item = QTableWidgetItem(f"{days_count} روز")
            days_item.setTextAlignment(Qt.AlignCenter)
            
            time_item = QTableWidgetItem(f"{shift.get('shift_start')} تا {shift.get('shift_end')}")
            time_item.setTextAlignment(Qt.AlignCenter)
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(5)

            edit_btn = QPushButton("ویرایش ✏️")
            edit_btn.setStyleSheet("background-color: #f39c12; color: white; padding: 4px; font-size: 11px;")
            edit_btn.clicked.connect(lambda _, s=shift: self.open_edit_shift(s))

            del_btn = QPushButton("حذف 🗑")
            del_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 4px; font-size: 11px;")
            del_btn.clicked.connect(lambda _, s_id=shift["id"]: self.delete_shift(s_id))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(del_btn)
            
            self.table.setItem(idx, 0, cam_item)
            self.table.setItem(idx, 1, days_item)
            self.table.setItem(idx, 2, time_item)
            self.table.setCellWidget(idx, 3, actions_widget)

    def open_edit_shift(self, shift_data):
        dialog = EditShiftDialog(shift_data, self.cam_map, self.current_shifts, self)
        if dialog.exec_() == QDialog.Accepted: self.load_shifts() 

    def add_new_shift(self):
        selected_days = [str(val) for val, chk in self.days_checkboxes.items() if chk.isChecked()]
        if not selected_days:
            QMessageBox.warning(self, "خطا", "لطفاً حداقل یک روز را انتخاب کنید.")
            return
        payload = {
            "camera_id": self.combo_camera.currentData(),
            "allowed_days": ",".join(selected_days),
            "shift_start": f"{self.start_h_cb.currentText()}:{self.start_m_cb.currentText()}",
            "shift_end": f"{self.end_h_cb.currentText()}:{self.end_m_cb.currentText()}"
        }
        warnings = validate_shift_logic(payload, self.current_shifts, cam_map=self.cam_map)
        if warnings:
            msg = "⚠️ هشدارهای منطقی زیر یافت شد:\n\n" + "\n".join([f"❌ {w}" for w in warnings]) + "\n\nآیا با این حال می‌خواهید این شیفت را ثبت کنید؟"
            reply = QMessageBox.warning(self, "تداخل یافت شد", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        try:
            res = requests.post(f"http://localhost:8000/employees/{self.worker_id}/shifts", json=payload)
            if res.status_code == 200: self.load_shifts() 
        except Exception as e: QMessageBox.critical(self, "خطا", str(e))

    def delete_shift(self, shift_id):
        try:
            requests.delete(f"http://localhost:8000/employees/shifts/{shift_id}")
            self.load_shifts()
        except Exception as e: QMessageBox.critical(self, "خطا", str(e))

class WorkersListPage(QWidget):
    switch_to_add_worker = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.cam_map = {}
        
        # 🔴 استخراج مقادیر واژگان داینامیک از حافظه رجیستری
        self.settings = QSettings("SmartVision", "AttendanceSystem")
        self.t_single = self.settings.value("term_singular", "کارگر")
        self.t_plural = self.settings.value("term_plural", "کارگران")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel(f"مدیریت و لیست {self.t_plural}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["آیدی", f"نام و نام خانوادگی {self.t_single}", "ارتباطات", "تاریخ ثبت", "عملیات سیستم"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnHidden(0, True) 
        self.table.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        add_btn = QPushButton(f"افزودن {self.t_single} جدید +")
        add_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px 20px; border-radius: 4px;")
        add_btn.clicked.connect(self.switch_to_add_worker.emit)
        bottom_layout.addWidget(add_btn)
        layout.addLayout(bottom_layout)

        self.load_workers_data()

    def showEvent(self, event):
        super().showEvent(event)
        self.t_single = self.settings.value("term_singular", "کارگر")
        self.t_plural = self.settings.value("term_plural", "کارگران")
        self.load_workers_data()

    def load_workers_data(self):
        self.thread = FetchWorkersThread()
        self.thread.workers_ready.connect(self.populate_table)
        self.thread.start()

    def populate_table(self, workers, cam_map):
        self.cam_map = cam_map
        self.table.setRowCount(0)
        for row_idx, worker in enumerate(workers):
            self.table.insertRow(row_idx)
            
            # ۱. ساخت آیتم‌های متنی
            id_item = QTableWidgetItem(str(worker["id"]))
            name_item = QTableWidgetItem(worker["name"])
            
            contact_str = f"ملی: {worker.get('national_id') or '---'}\nتماس: {worker.get('phone_number') or '---'}"
            contact_item = QTableWidgetItem(contact_str)
            
            date_str = worker["created_at"].split("T")[0] if "T" in worker["created_at"] else worker["created_at"]
            date_item = QTableWidgetItem(date_str)

            # ۲. وسط‌چین کردن اجباری و قرار دادن در ستون‌های مربوطه
            for col, item in enumerate([id_item, name_item, contact_item, date_item]):
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                self.table.setItem(row_idx, col, item)

            self.table.setRowHeight(row_idx, 50)

            # ۳. ساخت دکمه‌های عملیات
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(5)

            edit_btn = QPushButton("ویرایش مشخصات")
            edit_btn.setStyleSheet("background-color: #f39c12; color: white; font-size: 11px; padding: 4px;")
            edit_btn.clicked.connect(lambda checked, w=worker: self.edit_worker(w))

            shift_btn = QPushButton("مدیریت شیفت‌ها 🕒")
            shift_btn.setStyleSheet("background-color: #8e44ad; color: white; font-size: 11px; padding: 4px; font-weight: bold;")
            shift_btn.clicked.connect(lambda checked, w=worker: self.open_shifts_manager(w))

            delete_btn = QPushButton("حذف")
            delete_btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 11px; padding: 4px;")
            delete_btn.clicked.connect(lambda checked, w_id=worker["id"]: self.delete_worker(w_id))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(shift_btn)
            actions_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 4, actions_widget)

    def edit_worker(self, worker_data):
        dialog = EditWorkerBasicDialog(worker_data, self)
        if dialog.exec_() == QDialog.Accepted: self.load_workers_data()

    def open_shifts_manager(self, worker_data):
        dialog = ManageShiftsDialog(worker_data["id"], worker_data["name"], self.cam_map, self)
        dialog.exec_()

    def delete_worker(self, worker_id):
        # 🔴 بومی‌سازی داینامیک سوال پنجره حذف
        confirm = QMessageBox.question(self, "تایید", f"آیا از حذف {self.t_single} اطمینان دارید؟", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                requests.delete(f"http://localhost:8000/employees/{worker_id}")
                self.load_workers_data()
            except Exception as e: QMessageBox.critical(self, "خطا", str(e))