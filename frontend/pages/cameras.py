import requests
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton,
                             QMessageBox, QLabel, QDialog, QFormLayout, 
                             QLineEdit, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

# =================================================================
# 1. کلاس‌های پردازش پس‌زمینه (Threads) برای ارتباط با بک‌اند
# =================================================================

class FetchCamerasListThread(QThread):
    data_ready = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            response = requests.get("http://localhost:8000/cameras/")
            if response.status_code == 200:
                self.data_ready.emit(response.json())
            else:
                self.error_signal.emit("خطا در دریافت اطلاعات از سرور")
        except Exception as e:
            self.error_signal.emit(str(e))

class AddCameraThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            response = requests.post("http://localhost:8000/cameras/", json=self.payload)
            if response.status_code == 200:
                self.finished_signal.emit(True, "دوربین جدید با موفقیت در سیستم ثبت شد.")
            else:
                self.finished_signal.emit(False, "خطا از سمت سرور: دوربین ثبت نشد.")
        except Exception as e:
            self.finished_signal.emit(False, f"خطای ارتباطی:\n{str(e)}")

class EditCameraThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cam_id, payload):
        super().__init__()
        self.cam_id = cam_id
        self.payload = payload

    def run(self):
        try:
            response = requests.put(f"http://localhost:8000/cameras/{self.cam_id}", json=self.payload)
            if response.status_code == 200:
                self.finished_signal.emit(True, "اطلاعات دوربین با موفقیت ویرایش شد.")
            else:
                self.finished_signal.emit(False, "خطا از سمت سرور: ویرایش انجام نشد.")
        except Exception as e:
            self.finished_signal.emit(False, f"خطای ارتباطی:\n{str(e)}")

class DeleteCameraThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cam_id):
        super().__init__()
        self.cam_id = cam_id

    def run(self):
        try:
            response = requests.delete(f"http://localhost:8000/cameras/{self.cam_id}")
            if response.status_code == 200:
                self.finished_signal.emit(True, "دوربین با موفقیت از دیتابیس حذف شد.")
            else:
                self.finished_signal.emit(False, "خطا در حذف دوربین از سرور.")
        except Exception as e:
            self.finished_signal.emit(False, f"خطای ارتباطی:\n{str(e)}")

# =================================================================
# 2. پنجره‌های پاپ‌آپ (Dialogs) برای افزودن و ویرایش
# =================================================================

class AddCameraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("افزودن دوربین جدید")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(15)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("مثال: دوربین سالن تولید")
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["وب‌کم (webcam)", "فایل ویدیویی (video)", "تحت شبکه (rtsp)"])
        
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("آدرس RTSP یا آیدی وبکم (مثلا 0)")
        
        self.input_location = QLineEdit()
        self.input_location.setPlaceholderText("مثال: درب ورودی سوله 1")
        
        self.input_zone = QLineEdit()
        self.input_zone.setPlaceholderText("مختصات منطقه: 0, 0, 1280, 720")
        self.input_zone.setText("0, 0, 1280, 720") 
        
        self.combo_status = QComboBox()
        self.combo_status.addItems(["فعال (Active)", "غیرفعال (Inactive)"])

        layout.addRow("نام دوربین:", self.input_name)
        layout.addRow("نوع دوربین:", self.combo_type)
        layout.addRow("لینک (URL) یا آیدی:", self.input_url)
        layout.addRow("مکان (Location):", self.input_location)
        layout.addRow("زون تصویر:", self.input_zone)
        layout.addRow("وضعیت دوربین:", self.combo_status)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 ثبت دوربین")
        self.save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px;")
        self.save_btn.clicked.connect(self.submit_data)
        
        self.cancel_btn = QPushButton("انصراف")
        self.cancel_btn.setStyleSheet("background-color: #95a5a6; color: white; padding: 8px;")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addRow(btn_layout)

    def submit_data(self):
        name = self.input_name.text().strip()
        url = self.input_url.text().strip()
        location = self.input_location.text().strip()
        zone_str = self.input_zone.text().strip()

        if not name or not url:
            QMessageBox.warning(self, "اخطار", "نام دوربین و لینک (URL) الزامی هستند!")
            return

        type_mapping = {"وب‌کم (webcam)": "webcam", "فایل ویدیویی (video)": "video", "تحت شبکه (rtsp)": "rtsp"}
        cam_type = type_mapping.get(self.combo_type.currentText(), "webcam")
        is_active = True if "فعال" in self.combo_status.currentText() and "غیرفعال" not in self.combo_status.currentText() else False

        try:
            zones_list = [int(x.strip()) for x in zone_str.split(',')]
            if len(zones_list) != 4: raise ValueError
        except:
            QMessageBox.warning(self, "اخطار", "مختصات زون باید دقیقاً شامل 4 عدد با کاما باشد (مثال: 0,0,1280,720)")
            return

        payload = {
            "name": name,
            "type": cam_type,
            "rtsp_url": url,
            "location": location,
            "zones": zones_list,
            "is_active": is_active
        }

        self.save_btn.setEnabled(False)
        self.thread = AddCameraThread(payload)
        self.thread.finished_signal.connect(self.on_submit_finished)
        self.thread.start()

    def on_submit_finished(self, success, message):
        self.save_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "موفق", message)
            self.accept()
        else:
            QMessageBox.critical(self, "خطا", message)


class EditCameraDialog(QDialog):
    def __init__(self, cam_data, parent=None):
        super().__init__(parent)
        self.cam_id = cam_data["id"]
        self.setWindowTitle(f"ویرایش دوربین (آیدی: {self.cam_id})")
        self.setFixedWidth(400)
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QFormLayout(self)
        layout.setSpacing(15)

        self.input_name = QLineEdit(cam_data.get("name", ""))
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["وب‌کم (webcam)", "فایل ویدیویی (video)", "تحت شبکه (rtsp)"])
        # مپ کردن نوع دوربین فعلی برای نمایش درست در کومبوباکس
        type_reverse_map = {"webcam": "وب‌کم (webcam)", "video": "فایل ویدیویی (video)", "rtsp": "تحت شبکه (rtsp)"}
        current_type = type_reverse_map.get(cam_data.get("type", "webcam"))
        self.combo_type.setCurrentText(current_type)
        
        self.input_url = QLineEdit(cam_data.get("rtsp_url", ""))
        self.input_location = QLineEdit(cam_data.get("location", ""))
        
        # تبدیل آرایه زون به استرینگ
        zones_array = cam_data.get("zones", [0, 0, 1280, 720])
        zones_str = ", ".join(map(str, zones_array))
        self.input_zone = QLineEdit(zones_str)
        
        self.combo_status = QComboBox()
        self.combo_status.addItems(["فعال (Active)", "غیرفعال (Inactive)"])
        if cam_data.get("is_active", True):
            self.combo_status.setCurrentText("فعال (Active)")
        else:
            self.combo_status.setCurrentText("غیرفعال (Inactive)")

        layout.addRow("نام دوربین:", self.input_name)
        layout.addRow("نوع دوربین:", self.combo_type)
        layout.addRow("لینک (URL) یا آیدی:", self.input_url)
        layout.addRow("مکان (Location):", self.input_location)
        layout.addRow("زون تصویر:", self.input_zone)
        layout.addRow("وضعیت دوربین:", self.combo_status)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("🔄 ذخیره تغییرات")
        self.save_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 8px;")
        self.save_btn.clicked.connect(self.submit_data)
        
        self.cancel_btn = QPushButton("انصراف")
        self.cancel_btn.setStyleSheet("background-color: #95a5a6; color: white; padding: 8px;")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addRow(btn_layout)

    def submit_data(self):
        name = self.input_name.text().strip()
        url = self.input_url.text().strip()
        location = self.input_location.text().strip()
        zone_str = self.input_zone.text().strip()

        if not name or not url:
            QMessageBox.warning(self, "اخطار", "نام دوربین و لینک (URL) الزامی هستند!")
            return

        type_mapping = {"وب‌کم (webcam)": "webcam", "فایل ویدیویی (video)": "video", "تحت شبکه (rtsp)": "rtsp"}
        cam_type = type_mapping.get(self.combo_type.currentText(), "webcam")
        is_active = True if "فعال" in self.combo_status.currentText() and "غیرفعال" not in self.combo_status.currentText() else False

        try:
            zones_list = [int(x.strip()) for x in zone_str.split(',')]
            if len(zones_list) != 4: raise ValueError
        except:
            QMessageBox.warning(self, "اخطار", "مختصات زون باید دقیقاً شامل 4 عدد با کاما باشد")
            return

        payload = {
            "name": name,
            "type": cam_type,
            "rtsp_url": url,
            "location": location,
            "zones": zones_list,
            "is_active": is_active
        }

        self.save_btn.setEnabled(False)
        self.thread = EditCameraThread(self.cam_id, payload)
        self.thread.finished_signal.connect(self.on_submit_finished)
        self.thread.start()

    def on_submit_finished(self, success, message):
        self.save_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "موفق", message)
            self.accept()
        else:
            QMessageBox.critical(self, "خطا", message)

# =================================================================
# 3. کلاس اصلی صفحه مدیریت دوربین‌ها (UI اصلی)
# =================================================================

class CamerasPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("مدیریت و تنظیمات دوربین‌های سیستم")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)

        # جدول با 5 ستون (ستون جدید برای عملیات)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["آیدی", "نام / نوع دوربین", "موقعیت (Location)", "وضعیت فعالیت", "عملیات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) 
        self.table.setColumnWidth(4, 150) # عرض ثابت برای دکمه‌ها
        layout.addWidget(self.table)

        # دکمه افزودن دوربین
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        add_btn = QPushButton("افزودن دوربین جدید 🎥+")
        add_btn.setStyleSheet("""
            background-color: #3498db; 
            color: white; 
            font-weight: bold; 
            font-size: 14px; 
            padding: 10px 20px; 
            border-radius: 4px;
        """)
        add_btn.clicked.connect(self.open_add_dialog)
        bottom_layout.addWidget(add_btn)
        layout.addLayout(bottom_layout)

        self.load_cameras()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_cameras()

    def load_cameras(self):
        self.thread = FetchCamerasListThread()
        self.thread.data_ready.connect(self.populate_table)
        self.thread.error_signal.connect(self.show_error)
        self.thread.start()

    def populate_table(self, cameras):
        self.table.setRowCount(0)
        for row_idx, cam in enumerate(cameras):
            self.table.insertRow(row_idx)

            id_item = QTableWidgetItem(str(cam.get("id", "---")))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)
            
            cam_name = cam.get("name", "بدون نام")
            cam_type_raw = cam.get("type", "---")
            type_map = {"webcam": "وب‌کم", "video": "ویدیو", "rtsp": "تحت شبکه"}
            cam_type_text = type_map.get(cam_type_raw, cam_type_raw)
            
            name_type_str = f"{cam_name} ({cam_type_text})"
            type_item = QTableWidgetItem(name_type_str)
            type_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, type_item)
            
            loc_item = QTableWidgetItem(cam.get("location") or "نامشخص")
            loc_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, loc_item)
            
            is_active = cam.get("is_active", False)
            status_text = "فعال" if is_active else "غیرفعال"
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)
            
            if is_active:
                status_item.setForeground(QBrush(QColor("#2ecc71")))
            else:
                status_item.setForeground(QBrush(QColor("#95a5a6")))
                
            self.table.setItem(row_idx, 3, status_item)

            # --- ساخت دکمه‌های عملیات (ویرایش و حذف) ---
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 2, 5, 2)
            actions_layout.setSpacing(5)

            edit_btn = QPushButton("ویرایش ✏️")
            edit_btn.setStyleSheet("background-color: #f39c12; color: white; padding: 4px; font-size: 11px;")
            edit_btn.clicked.connect(lambda checked, c=cam: self.open_edit_dialog(c))

            delete_btn = QPushButton("حذف 🗑")
            delete_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 4px; font-size: 11px;")
            delete_btn.clicked.connect(lambda checked, c_id=cam["id"]: self.delete_camera(c_id))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 4, actions_widget)

    def show_error(self, error_msg):
        QMessageBox.warning(self, "خطا", f"خطا در بارگذاری لیست دوربین‌ها:\n{error_msg}")

    def open_add_dialog(self):
        dialog = AddCameraDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_cameras() 

    def open_edit_dialog(self, cam_data):
        dialog = EditCameraDialog(cam_data, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_cameras() 

    def delete_camera(self, cam_id):
        # دیالوگ تاییدیه قبل از حذف
        reply = QMessageBox.question(
            self, 'تایید حذف', 
            f"آیا از حذف دائم دوربین شماره {cam_id} اطمینان دارید؟\nاین عملیات غیرقابل بازگشت است.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.del_thread = DeleteCameraThread(cam_id)
            self.del_thread.finished_signal.connect(self.on_delete_finished)
            self.del_thread.start()

    def on_delete_finished(self, success, message):
        if success:
            QMessageBox.information(self, "حذف موفق", message)
            self.load_cameras()
        else:
            QMessageBox.critical(self, "خطا", message)