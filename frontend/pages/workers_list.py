import os
import shutil
import requests
from pathlib import Path
import cv2
from insightface.app import FaceAnalysis

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QMessageBox, QDialog, QLineEdit, QFormLayout, 
                             QLabel, QComboBox, QCheckBox, QGridLayout, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKERS_DIR = BASE_DIR / "data" / "workers"

# =================================================================
# 1. Threads
# =================================================================
class FetchWorkersThread(QThread):
    workers_ready = pyqtSignal(list, dict) 
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            cam_res = requests.get("http://localhost:8000/cameras/")
            cam_map = {}
            if cam_res.status_code == 200:
                for c in cam_res.json(): cam_map[c["id"]] = c["name"]

            response = requests.get("http://localhost:8000/employees/")
            if response.status_code == 200:
                self.workers_ready.emit(response.json(), cam_map)
            else:
                self.error_occurred.emit("خطا در دریافت کارگران")
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
            if res.status_code == 200:
                self.finished_signal.emit(True, "اطلاعات با موفقیت ویرایش شد.")
            else:
                self.finished_signal.emit(False, "خطا در سرور")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

# =================================================================
# پاپ‌آپ ویرایش یک شیفت خاص (کلاس جدید)
# =================================================================
class EditShiftDialog(QDialog):
    def __init__(self, shift_data, cam_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ویرایش شیفت")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.shift_data = shift_data
        self.cam_map = cam_map

        layout = QFormLayout(self)

        self.combo_camera = QComboBox()
        self.combo_camera.addItem("همه دوربین‌ها", None)
        for c_id, c_name in self.cam_map.items():
            self.combo_camera.addItem(c_name, c_id)

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
            if str(day_val) in saved_days:
                chk.setChecked(True)
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
        
        try:
            res = requests.put(f"http://localhost:8000/employees/shifts/{self.shift_data['id']}", json=payload)
            if res.status_code == 200:
                self.accept()
            else:
                QMessageBox.critical(self, "خطا", f"خطای سرور: {res.text}")
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))

# =================================================================
# پنل مستقل مدیریت شیفت‌ها (آپدیت شده)
# =================================================================
class ManageShiftsDialog(QDialog):
    def __init__(self, worker_id, worker_name, cam_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"مدیریت شیفت‌ها - {worker_name}")
        self.setFixedSize(550, 500) # کمی بزرگتر شد تا جدول بهتر جا شود
        self.setLayoutDirection(Qt.RightToLeft)
        
        self.worker_id = worker_id
        self.cam_map = cam_map

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["دوربین", "روزها", "ساعت", "عملیات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # 🔴 لیبل راهنمای اضافه شده
        add_title = QLabel("--- ✨ افزودن شیفت جدید ✨ ---")
        add_title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px; margin-top: 10px;")
        add_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(add_title)

        add_group = QFormLayout()
        
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("همه دوربین‌ها", None)
        for c_id, c_name in self.cam_map.items():
            self.combo_camera.addItem(c_name, c_id)
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
                worker_data = res.json()
                shifts = [s for s in worker_data.get("shifts", []) if not s.get("is_deleted", False)]
                self.populate_table(shifts)
        except Exception as e:
            print("Error loading shifts:", e)

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
            
            # 🔴 دکمه‌های عملیات (اضافه شدن دکمه ویرایش)
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
        dialog = EditShiftDialog(shift_data, self.cam_map, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_shifts() # رفرش اتوماتیک لیست شیفت‌ها پس از ویرایش

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
        try:
            res = requests.post(f"http://localhost:8000/employees/{self.worker_id}/shifts", json=payload)
            if res.status_code == 200:
                self.load_shifts() 
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))

    def delete_shift(self, shift_id):
        try:
            requests.delete(f"http://localhost:8000/employees/shifts/{shift_id}")
            self.load_shifts()
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))

# =================================================================
# 3. پاپ‌آپ ویرایش سریع (فقط متون هویتی)
# =================================================================
class EditWorkerBasicDialog(QDialog):
    def __init__(self, worker_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ویرایش اطلاعات هویتی")
        self.setFixedWidth(300)
        self.setLayoutDirection(Qt.RightToLeft)
        self.worker_id = worker_data["id"]

        layout = QFormLayout(self)
        self.name_input = QLineEdit(worker_data["name"])
        self.national_id_input = QLineEdit(worker_data.get("national_id") or "")
        self.phone_input = QLineEdit(worker_data.get("phone_number") or "")

        layout.addRow("نام کامل:", self.name_input)
        layout.addRow("کد ملی:", self.national_id_input)
        layout.addRow("تلفن همراه:", self.phone_input)

        save_btn = QPushButton("ذخیره تغییرات متنی")
        save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self.submit)
        layout.addRow(save_btn)

    def submit(self):
        payload = {
            "name": self.name_input.text().strip(),
            "national_id": self.national_id_input.text().strip(),
            "phone_number": self.phone_input.text().strip()
        }
        self.thread = EditWorkerTextThread(self.worker_id, payload)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()

    def on_finished(self, success, msg):
        if success: self.accept()
        else: QMessageBox.critical(self, "خطا", msg)

# =================================================================
# 4. کلاس اصلی صفحه لیست کارگران
# =================================================================
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

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["آیدی", "نام و نام خانوادگی", "ارتباطات", "تاریخ ثبت", "عملیات سیستم"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnHidden(0, True) 
        self.table.setColumnWidth(4, 250)
        self.table.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        add_btn = QPushButton("افزودن کارگر جدید +")
        add_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px 20px; border-radius: 4px;")
        add_btn.clicked.connect(self.switch_to_add_worker.emit)
        bottom_layout.addWidget(add_btn)
        layout.addLayout(bottom_layout)

        self.load_workers_data()

    def showEvent(self, event):
        super().showEvent(event)
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

            id_item = QTableWidgetItem(str(worker["id"]))
            name_item = QTableWidgetItem(worker["name"])
            
            contact_str = f"ملی: {worker.get('national_id') or '---'}\nتماس: {worker.get('phone_number') or '---'}"
            contact_item = QTableWidgetItem(contact_str)
            
            date_str = worker["created_at"].split("T")[0] if "T" in worker["created_at"] else worker["created_at"]
            date_item = QTableWidgetItem(date_str)

            for col, item in enumerate([id_item, name_item, contact_item, date_item]):
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col, item)

            self.table.setRowHeight(row_idx, 50)

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
        if dialog.exec_() == QDialog.Accepted:
            self.load_workers_data()

    def open_shifts_manager(self, worker_data):
        dialog = ManageShiftsDialog(worker_data["id"], worker_data["name"], self.cam_map, self)
        dialog.exec_()

    def delete_worker(self, worker_id):
        confirm = QMessageBox.question(self, "تایید", "آیا از حذف کارگر اطمینان دارید؟", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                requests.delete(f"http://localhost:8000/employees/{worker_id}")
                self.load_workers_data()
            except Exception as e:
                QMessageBox.critical(self, "خطا", str(e))