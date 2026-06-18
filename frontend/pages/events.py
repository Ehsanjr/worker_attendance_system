import requests
import csv
from datetime import datetime, timedelta
from pathlib import Path

# استفاده از کتابخانه شمسی برای کل محاسبات
import jdatetime

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QMessageBox, QLabel, QLineEdit, QComboBox, 
                             QFileDialog, QCompleter, QDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont, QTextDocument
from PyQt5.QtPrintSupport import QPrinter

# =================================================================
# ۰. دیالوگ پاپ‌آپ اختصاصی برای انتخاب تاریخ و زمان شمسی
# =================================================================
class ShamsiDatePickerDialog(QDialog):
    def __init__(self, initial_jdt, parent=None):
        super().__init__(parent)
        self.setWindowTitle("انتخاب تاریخ و زمان")
        self.setFixedSize(380, 150)
        self.setLayoutDirection(Qt.RightToLeft)

        self.selected_jdt = initial_jdt

        layout = QVBoxLayout(self)

        # --- بخش تاریخ ---
        date_layout = QHBoxLayout()
        
        self.year_cb = QComboBox()
        self.year_cb.addItems([str(y) for y in range(1400, 1421)])
        self.year_cb.setCurrentText(str(initial_jdt.year))

        self.month_cb = QComboBox()
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        self.month_cb.addItems(months)
        self.month_cb.setCurrentIndex(initial_jdt.month - 1)

        self.day_cb = QComboBox()
        self.day_cb.addItems([str(d) for d in range(1, 32)])
        self.day_cb.setCurrentText(str(initial_jdt.day))

        date_layout.addWidget(QLabel("سال:"))
        date_layout.addWidget(self.year_cb)
        date_layout.addWidget(QLabel("ماه:"))
        date_layout.addWidget(self.month_cb)
        date_layout.addWidget(QLabel("روز:"))
        date_layout.addWidget(self.day_cb)
        layout.addLayout(date_layout)

        # --- بخش زمان ---
        time_layout = QHBoxLayout()
        
        self.hour_cb = QComboBox()
        self.hour_cb.addItems([f"{h:02d}" for h in range(24)])
        self.hour_cb.setCurrentText(f"{initial_jdt.hour:02d}")

        self.min_cb = QComboBox()
        self.min_cb.addItems([f"{m:02d}" for m in range(60)])
        self.min_cb.setCurrentText(f"{initial_jdt.minute:02d}")

        time_layout.addWidget(QLabel("ساعت:"))
        time_layout.addWidget(self.hour_cb)
        time_layout.addWidget(QLabel(":"))
        time_layout.addWidget(self.min_cb)
        time_layout.addStretch()
        layout.addLayout(time_layout)

        # --- دکمه‌ها ---
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("تایید و اعمال فیلتر")
        save_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 6px;")
        save_btn.clicked.connect(self.accept_date)
        
        cancel_btn = QPushButton("انصراف")
        cancel_btn.setStyleSheet("background-color: #95a5a6; color: white; padding: 6px;")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def accept_date(self):
        y = int(self.year_cb.currentText())
        m = self.month_cb.currentIndex() + 1
        d = int(self.day_cb.currentText())
        h = int(self.hour_cb.currentText())
        minute = int(self.min_cb.currentText())

        try:
            # بررسی صحت تاریخ (مثلا کاربر ۳۱ اسفند انتخاب نکرده باشد)
            self.selected_jdt = jdatetime.datetime(y, m, d, h, minute)
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "خطا", "تاریخ انتخاب شده نامعتبر است (مثلاً این ماه ۳۱ روز ندارد).")

# =================================================================
# ۱. پردازشگر پیش‌زمینه (استخراج همزمان رخدادها، دوربین‌ها و کارگران)
# =================================================================
class FetchAbsencesThread(QThread):
    data_ready = pyqtSignal(list, dict, dict) 
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            cam_res = requests.get("http://localhost:8000/cameras/")
            cam_map = {}
            if cam_res.status_code == 200:
                for c in cam_res.json():
                    cam_map[c["id"]] = c.get("location") or c.get("name") or f"دوربین {c['id']}"

            emp_res = requests.get("http://localhost:8000/employees/")
            emp_map = {}
            if emp_res.status_code == 200:
                for e in emp_res.json():
                    emp_map[e["id"]] = e["name"]

            response = requests.get("http://localhost:8000/attendance/")
            if response.status_code != 200:
                self.error_occurred.emit("خطا در دریافت رخدادها از سرور.")
                return

            raw_events = response.json()
            raw_events.sort(key=lambda x: x.get("timestamp", ""))

            events_by_worker = {}
            for ev in raw_events:
                emp_id = ev.get("employee_id")
                if emp_id is not None:
                    events_by_worker.setdefault(emp_id, []).append(ev)

            absences_list = []
            id_counter = 1

            for emp_id, ev_list in events_by_worker.items():
                worker_name = emp_map.get(emp_id, f"کارگر ناشناس (آیدی: {emp_id})")
                absence_start_time = None
                last_camera_id = None

                for ev in ev_list:
                    ev_type = str(ev.get("event_type") or ev.get("status") or "").lower()
                    cam_id = ev.get("camera_id")
                    
                    t_str = ev.get("timestamp", "").replace("T", " ").replace("Z", "").split(".")[0]
                    try:
                        dt_obj = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
                    except: 
                        continue

                    if ev_type in ["exit", "out"]:
                        if absence_start_time == None:
                            absence_start_time = dt_obj
                            last_camera_id = cam_id
                    
                    elif ev_type in ["enter", "in"]:
                        if absence_start_time is not None:
                            absences_list.append({
                                "id": id_counter,
                                "worker_name": worker_name,
                                "camera_id": last_camera_id,
                                "camera_location": cam_map.get(last_camera_id, f"دوربین {last_camera_id}"),
                                "start_dt": absence_start_time,
                                "end_dt": dt_obj,
                            })
                            id_counter += 1
                            absence_start_time = None

                if absence_start_time is not None:
                    absences_list.append({
                        "id": id_counter,
                        "worker_name": worker_name,
                        "camera_id": last_camera_id,
                        "camera_location": cam_map.get(last_camera_id, f"دوربین {last_camera_id}"),
                        "start_dt": absence_start_time,
                        "end_dt": None, 
                    })
                    id_counter += 1

            absences_list.sort(key=lambda x: x["start_dt"], reverse=True)
            self.data_ready.emit(absences_list, cam_map, emp_map)

        except Exception as e:
            self.error_occurred.emit(str(e))

# =================================================================
# ۲. کلاس اصلی صفحه گزارشات هوشمند
# =================================================================
class EventsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.all_absences = [] 

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("گزارشات تحلیلی و بازه‌های غیبت کارگران")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title_label)

        # ---------------- پنل فیلترها ----------------
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.txt_filter_name = QLineEdit()
        self.txt_filter_name.setPlaceholderText("🔍 جستجوی نام کارگر...")
        self.txt_filter_name.setFixedWidth(150)
        self.txt_filter_name.textChanged.connect(self.apply_ui_filters)
        filter_layout.addWidget(self.txt_filter_name)

        self.combo_filter_cam = QComboBox()
        self.combo_filter_cam.setFixedWidth(140)
        self.combo_filter_cam.currentIndexChanged.connect(self.apply_ui_filters)
        filter_layout.addWidget(self.combo_filter_cam)

        # متغیرهای نگه‌داری زمان انتخابی
        now_dt = datetime.now()
        self.j_from_dt = jdatetime.datetime.fromgregorian(datetime=now_dt - timedelta(days=7))
        self.j_to_dt = jdatetime.datetime.fromgregorian(datetime=now_dt + timedelta(days=1))

        # دکمه‌های باز کننده پاپ‌آپ انتخاب تاریخ
        filter_layout.addWidget(QLabel("از:"))
        self.btn_date_from = QPushButton(self.j_from_dt.strftime("%Y/%m/%d - %H:%M"))
        self.btn_date_from.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; padding: 4px;")
        self.btn_date_from.clicked.connect(self.pick_from_date)
        filter_layout.addWidget(self.btn_date_from)

        filter_layout.addWidget(QLabel("تا:"))
        self.btn_date_to = QPushButton(self.j_to_dt.strftime("%Y/%m/%d - %H:%M"))
        self.btn_date_to.setStyleSheet("background-color: white; border: 1px solid #bdc3c7; padding: 4px;")
        self.btn_date_to.clicked.connect(self.pick_to_date)
        filter_layout.addWidget(self.btn_date_to)

        # دکمه‌های خروجی
        self.btn_export_excel = QPushButton("خروجی اکسل 🟢")
        self.btn_export_excel.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px;")
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        
        self.btn_export_pdf = QPushButton("خروجی PDF 🔴")
        self.btn_export_pdf.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 6px 12px;")
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)

        filter_layout.addStretch()
        filter_layout.addWidget(self.btn_export_excel)
        filter_layout.addWidget(self.btn_export_pdf)
        main_layout.addLayout(filter_layout)

        # ---------------- جدول اصلی ----------------
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "آیدی", "نام کارگر", "موقعیت دوربین", "زمان آغاز غیبت", "زمان پایان غیبت", "مدت زمان غیبت"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnHidden(0, True)
        main_layout.addWidget(self.table)

        self.load_data()

    # =================================================================
    # توابع باز کردن دیالوگ انتخاب تاریخ
    # =================================================================
    def pick_from_date(self):
        dlg = ShamsiDatePickerDialog(self.j_from_dt, self)
        if dlg.exec_() == QDialog.Accepted:
            self.j_from_dt = dlg.selected_jdt
            self.btn_date_from.setText(self.j_from_dt.strftime("%Y/%m/%d - %H:%M"))
            self.apply_ui_filters() # اعمال آنی فیلتر

    def pick_to_date(self):
        dlg = ShamsiDatePickerDialog(self.j_to_dt, self)
        if dlg.exec_() == QDialog.Accepted:
            self.j_to_dt = dlg.selected_jdt
            self.btn_date_to.setText(self.j_to_dt.strftime("%Y/%m/%d - %H:%M"))
            self.apply_ui_filters() # اعمال آنی فیلتر

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

    def load_data(self):
        self.thread = FetchAbsencesThread()
        self.thread.data_ready.connect(self.on_data_loaded)
        self.thread.error_occurred.connect(lambda err: QMessageBox.warning(self, "خطا", err))
        self.thread.start()

    def on_data_loaded(self, absences, cam_map, emp_map):
        self.all_absences = absences
        
        self.combo_filter_cam.blockSignals(True)
        self.combo_filter_cam.clear()
        self.combo_filter_cam.addItem("همه دوربین‌ها", None)
        for c_id, c_name in cam_map.items():
            self.combo_filter_cam.addItem(c_name, c_id)
        self.combo_filter_cam.blockSignals(False)

        worker_names = list(emp_map.values())
        completer = QCompleter(worker_names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains) 
        self.txt_filter_name.setCompleter(completer)

        self.apply_ui_filters()

    # =================================================================
    # اعمال فیلترینگ، ترشولد دوگانه (حذف نویز) و رنگ‌بندی
    # =================================================================
    def apply_ui_filters(self):
        name_query = self.txt_filter_name.text().strip().lower()
        target_cam_id = self.combo_filter_cam.currentData()
        
        # تبدیل زمان شمسی به میلادی برای مقایسه
        try:
            from_dt = self.j_from_dt.togregorian()
            to_dt = self.j_to_dt.togregorian()
        except:
            from_dt = datetime.min
            to_dt = datetime.max

        self.table.setRowCount(0)
        row_idx = 0
        
        IGNORE_THRESHOLD_MINUTES = 2  # ترشولد حذف نویز (زیر ۲ دقیقه کلا حذف می‌شود)
        DANGER_THRESHOLD_MINUTES = 15 # ترشولد خطر (بالای ۱۵ دقیقه قرمز می‌شود)

        for abs_rec in self.all_absences:
            # ۱. فیلترهای جستجوی کاربر (نام، دوربین، تاریخ)
            if name_query and name_query not in abs_rec["worker_name"].lower():
                continue
            if target_cam_id is not None and abs_rec["camera_id"] != target_cam_id:
                continue
            if not (from_dt <= abs_rec["start_dt"] <= to_dt):
                continue

            # ۲. 🔴 منطق ترشولد ۲ دقیقه‌ای (فیلتر نویزها)
            if abs_rec["end_dt"] is not None:
                # غیبت تمام شده است -> محاسبه زمان رفت و برگشت
                delta = abs_rec["end_dt"] - abs_rec["start_dt"]
                if delta.total_seconds() < (IGNORE_THRESHOLD_MINUTES * 60):
                    continue # غیبت زیر ۲ دقیقه کلا در جدول رسم نمی‌شود (رد شدن از حلقه)
            else:
                # کارگر همچنان غایب است -> تا ۲ دقیقه اول او را نشان نده تا داشبورد چشمک نزند
                live_delta = datetime.now() - abs_rec["start_dt"]
                if live_delta.total_seconds() < (IGNORE_THRESHOLD_MINUTES * 60):
                    continue 

            # اگر از فیلترها رد شد (یعنی غیبت بالای ۲ دقیقه است)، سطر را ایجاد کن
            self.table.insertRow(row_idx)

            start_shamsi = self.to_shamsi(abs_rec["start_dt"])
            end_shamsi = self.to_shamsi(abs_rec["end_dt"])
            duration_text = self.calculate_duration_str(abs_rec["start_dt"], abs_rec["end_dt"])

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(abs_rec["id"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(abs_rec["worker_name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(abs_rec["camera_location"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(start_shamsi))
            
            end_item = QTableWidgetItem(end_shamsi)
            dur_item = QTableWidgetItem(duration_text)

            # ۳. 🔴 رنگ‌بندی بر اساس ترشولد ۱۵ دقیقه‌ای
            if abs_rec["end_dt"] is None:
                # حالت اول: همچنان غایب (بیش از ۲ دقیقه)
                end_item.setForeground(QBrush(QColor("#e74c3c")))
                end_item.setFont(QFont("Tahoma", -1, QFont.Bold))
                dur_item.setForeground(QBrush(QColor("#e74c3c")))
                dur_item.setFont(QFont("Tahoma", -1, QFont.Bold))
            else:
                delta = abs_rec["end_dt"] - abs_rec["start_dt"]
                # چون زیر ۲ دقیقه را بالا فیلتر کردیم، اینجا قطعاً زمان بالای ۲ دقیقه است
                if delta.total_seconds() <= (DANGER_THRESHOLD_MINUTES * 60):
                    # حالت دوم: بین ۲ تا ۱۵ دقیقه -> سبز
                    dur_item.setForeground(QBrush(QColor("#2ecc71")))
                    dur_item.setFont(QFont("Tahoma", -1, QFont.Bold))
                else:
                    # حالت سوم: بیشتر از ۱۵ دقیقه -> قرمز
                    dur_item.setForeground(QBrush(QColor("#e74c3c")))
                    dur_item.setFont(QFont("Tahoma", -1, QFont.Bold))

            self.table.setItem(row_idx, 4, end_item)
            self.table.setItem(row_idx, 5, dur_item)

            for col in [0, 2, 3, 4, 5]:
                item = self.table.item(row_idx, col)
                if item: item.setTextAlignment(Qt.AlignCenter)

            row_idx += 1

    # =================================================================
    # توابع کمکی
    # =================================================================
    def to_shamsi(self, dt_obj):
        if dt_obj is None:
            return "همچنان غایب 🏃‍♂️"
        j_dt = jdatetime.datetime.fromgregorian(datetime=dt_obj)
        return j_dt.strftime("%Y/%m/%d - %H:%M")

    def calculate_duration_str(self, start_dt, end_dt):
        end = end_dt if end_dt is not None else datetime.now()
        delta = end - start_dt

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days > 0: parts.append(f"{days} روز")
        if hours > 0: parts.append(f"{hours} ساعت")
        if minutes > 0: parts.append(f"{minutes} دقیقه")

        return " و ".join(parts) if parts else "کمتر از یک دقیقه"

    # =================================================================
    # خروجی‌ها
    # =================================================================
    def export_to_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل اکسل", "", "Excel CSV (*.csv)")
        if not path: return
        try:
            with open(path, mode='w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["نام کارگر", "موقعیت دوربین", "زمان آغاز غیبت", "زمان پایان غیبت", "مدت زمان غیبت"])
                for row in range(self.table.rowCount()):
                    writer.writerow([self.table.item(row, c).text() for c in range(1, 6)])
            QMessageBox.information(self, "موفق", "گزارش اکسل با موفقیت ذخیره شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ساخت فایل اکسل:\n{str(e)}")

    def export_to_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل PDF", "", "PDF Files (*.pdf)")
        if not path: return
        try:
            printer = QPrinter() 
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setPaperSize(QPrinter.A4)
            printer.setOrientation(QPrinter.Portrait)
            printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
            printer.setOutputFileName(path)

            html = """
            <div dir="rtl" style="font-family: Tahoma, sans-serif; padding: 10px;">
                <h2 style="text-align: center; color: #2c3e50; font-size: 20px; margin-bottom: 5px;">گزارش بازه‌های غیبت کارگران</h2>
                <p style="text-align: center; font-size: 11px; color: #7f8c8d;">تاریخ استخراج: """ + self.to_shamsi(datetime.now()) + """</p>
                <hr style="border: 0.5px solid #bdc3c7; margin-bottom: 20px;">
                <table border="1" cellspacing="0" cellpadding="8" style="width: 100%; border-collapse: collapse; text-align: center; font-size: 13px;">
                    <tr style="background-color: #34495e; color: white; font-weight: bold;">
                        <th style="padding: 10px;">ردیف</th>
                        <th>نام کارگر</th>
                        <th>موقعیت دوربین</th>
                        <th>زمان آغاز غیبت</th>
                        <th>زمان پایان غیبت</th>
                        <th>مدت غیبت</th>
                    </tr>
            """
            for row in range(self.table.rowCount()):
                bg_color = "#f9f9f9" if row % 2 == 0 else "#ffffff"
                html += f"""
                    <tr style="background-color: {bg_color};">
                        <td style="padding: 8px;">{row + 1}</td>
                        <td style="text-align: right; padding-right: 10px;">{self.table.item(row, 1).text()}</td>
                        <td>{self.table.item(row, 2).text()}</td>
                        <td>{self.table.item(row, 3).text()}</td>
                        <td>{self.table.item(row, 4).text()}</td>
                        <td style="color: #d35400; font-weight: bold;">{self.table.item(row, 5).text()}</td>
                    </tr>
                """

            html += "</table></div>"
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)
            QMessageBox.information(self, "موفق", "فایل گزارش PDF با موفقیت ساخته شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ساخت فایل PDF:\n{str(e)}")