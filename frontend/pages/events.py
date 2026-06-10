import os
import requests
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, 
                             QMessageBox, QComboBox, QLabel, QStackedWidget, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextDocument, QColor, QBrush, QFont
from PyQt5.QtPrintSupport import QPrinter

# -----------------------------------------------------------------
# Thread برای بارگذاری همزمان اطلاعات و جلوگیری از فریز شدن UI
# -----------------------------------------------------------------
class LoadEventsThread(QThread):
    data_ready = pyqtSignal(list, dict, dict)
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            # ۱. دریافت لیست کارگران برای مپ کردن آیدی به اسم
            workers_map = {}
            w_res = requests.get("http://localhost:8000/employees/")
            if w_res.status_code == 200:
                for w in w_res.json():
                    workers_map[w["id"]] = w["name"]

            # ۲. دریافت لیست دوربین‌ها برای مپ کردن آیدی به لوکیشن
            cameras_map = {}
            c_res = requests.get("http://localhost:8000/cameras/")
            if c_res.status_code == 200:
                for c in c_res.json():
                    cameras_map[c["id"]] = c.get("location") or c.get("name") or "نامشخص"

            # ۳. دریافت کل رخدادها
            e_res = requests.get("http://localhost:8000/attendance/")
            events = e_res.json() if e_res.status_code == 200 else []

            self.data_ready.emit(events, workers_map, cameras_map)
        except Exception as e:
            self.error_signal.emit(str(e))

# -----------------------------------------------------------------
# کلاس اصلی صفحه رخدادها
# -----------------------------------------------------------------
class EventsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        
        # متغیرهای ذخیره داده‌ها
        self.all_events = []
        self.workers_map = {}
        self.cameras_map = {}
        self.current_view = "all" # می تواند all یا absences باشد

        # لایوت اصلی
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # ---------------------------------------------------------
        # نوار ابزار بالا (فیلترها و دکمه‌های خروجی)
        # ---------------------------------------------------------
        top_bar = QHBoxLayout()
        
        # فیلتر کارگر
        top_bar.addWidget(QLabel("فیلتر کارگر:"))
        self.worker_combo = QComboBox()
        self.worker_combo.setFixedWidth(180)
        self.worker_combo.currentIndexChanged.connect(self.filter_data)
        top_bar.addWidget(self.worker_combo)
        
        top_bar.addSpacing(15)

        # دکمه محاسبه غیبت‌ها (کامپاند کاملاً هوشمند)
        self.btn_toggle_view = QPushButton("📊 محاسبه مدت زمان غیبت")
        self.btn_toggle_view.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 7px 15px;")
        self.btn_toggle_view.clicked.connect(self.toggle_view)
        top_bar.addWidget(self.btn_toggle_view)

        top_bar.addStretch() # هل دادن دکمه‌های خروجی به سمت چپ

        # دکمه‌های اکسل و PDF
        self.btn_excel = QPushButton("خروجی اکسل 📄")
        self.btn_excel.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 7px 15px;")
        self.btn_excel.clicked.connect(self.export_to_excel)
        
        self.btn_pdf = QPushButton("خروجی پی‌دی‌اف 🟥")
        self.btn_pdf.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 7px 15px;")
        self.btn_pdf.clicked.connect(self.export_to_pdf)

        top_bar.addWidget(self.btn_excel)
        top_bar.addWidget(self.btn_pdf)
        main_layout.addLayout(top_bar)

        # ---------------------------------------------------------
        # بخش جداول (Stacked Widget)
        # ---------------------------------------------------------
        self.table_stack = QStackedWidget()
        main_layout.addWidget(self.table_stack)

        # جدول شماره ۱: کل رخدادها
        self.table_all = QTableWidget()
        self.table_all.setColumnCount(5)
        self.table_all.setHorizontalHeaderLabels(["آیدی رخداد", "اسم کارگر", "موقعیت دوربین", "نوع رخداد", "زمان دقیق"])
        self.table_all.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_stack.addWidget(self.table_all)

        # جدول شماره ۲: غیبت‌ها
        self.table_absences = QTableWidget()
        self.table_absences.setColumnCount(5)
        self.table_absences.setHorizontalHeaderLabels(["ردیف", "اسم کارگر", "مدت زمان غیبت", "تاریخ و زمان غیبت", "لوکیشن دوربین"])
        self.table_absences.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_stack.addWidget(self.table_absences)

        # بارگذاری اولیه داده‌ها
        self.refresh_data()

    def refresh_data(self):
        self.thread = LoadEventsThread()
        self.thread.data_ready.connect(self.on_data_loaded)
        self.thread.error_signal.connect(lambda msg: QMessageBox.critical(self, "خطا", f"خطا در لود داده: {msg}"))
        self.thread.start()

    def on_data_loaded(self, events, workers_map, cameras_map):
        self.all_events = events
        self.workers_map = workers_map
        self.cameras_map = cameras_map

        # پر کردن کومبوباکس فیلتر کارگران
        self.worker_combo.blockSignals(True)
        self.worker_combo.clear()
        self.worker_combo.addItem("همه کارگران", None)
        for w_id, w_name in self.workers_map.items():
            self.worker_combo.addItem(w_name, w_id)
        self.worker_combo.blockSignals(False)

        self.filter_data()

    def toggle_view(self):
        """سوئیچ بین جدول کل رخدادها و جدول غیبت‌ها"""
        if self.current_view == "all":
            self.current_view = "absences"
            self.btn_toggle_view.setText("👁 مشاهده همه رخدادها")
            self.btn_toggle_view.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; padding: 7px 15px;")
            self.table_stack.setCurrentIndex(1) # نمایش جدول غیبت‌ها
        else:
            self.current_view = "all"
            self.btn_toggle_view.setText("📊 محاسبه مدت زمان غیبت")
            self.btn_toggle_view.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 7px 15px;")
            self.table_stack.setCurrentIndex(0) # نمایش جدول رخدادها
        
        self.filter_data()

    def filter_data(self):
        """فیلتر و پردازش هوشمند آرایه‌ها بر اساس کارگر انتخاب شده"""
        selected_worker_id = self.worker_combo.currentData()

        # ۱. فیلتر کردن رخدادهای خام بر اساس کارگر
        filtered_events = self.all_events
        if selected_worker_id is not None:
            filtered_events = [e for e in self.all_events if e.get("employee_id") == selected_worker_id]

        # مرتب‌سازی رخدادها بر اساس زمان برای پایداری محاسبات غیبت
        filtered_events = sorted(filtered_events, key=lambda x: x.get("timestamp", ""))

        if self.current_view == "all":
            self.populate_all_events_table(filtered_events)
        else:
            self.populate_absences_table(filtered_events, selected_worker_id)

    def populate_all_events_table(self, events):
        self.table_all.setRowCount(0)
        for row_idx, ev in enumerate(events):
            self.table_all.insertRow(row_idx)
            
            # استخراج نام کارگر و لوکیشن دوربین از روی دیکشنری مپینگ
            worker_name = self.workers_map.get(ev.get("employee_id"), f"کارگر {ev.get('employee_id')}")
            camera_loc = self.cameras_map.get(ev.get("camera_id"), "لوکیشن نامشخص")
            
            status_raw = ev.get("event_type") or ev.get("status") or ev.get("type") or "---"
            status_text = "ورود" if status_raw.upper() in ["IN", "ENTER"] else "خروج" if status_raw.upper() in ["OUT", "EXIT", "ABSENT"] else status_raw

            time_str = ev.get("timestamp", "---").replace("T", "  ").split(".")[0]

            self.table_all.setItem(row_idx, 0, QTableWidgetItem(str(ev.get("id", "---"))))
            self.table_all.setItem(row_idx, 1, QTableWidgetItem(worker_name))
            self.table_all.setItem(row_idx, 2, QTableWidgetItem(camera_loc))
            
            status_item = QTableWidgetItem(status_text)
            
            # --- تنظیم فونت بولد ---
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)
            
            # --- تنظیم رنگ متن (Foreground) به جای استایل‌شیت ---
            if status_raw.upper() in ["IN", "ENTER"]:
                status_item.setForeground(QBrush(QColor("#2ecc71"))) # رنگ سبز برای ورود
            elif status_raw.upper() in ["OUT", "EXIT", "ABSENT"]:
                status_item.setForeground(QBrush(QColor("#e74c3c"))) # رنگ قرمز برای خروج و غیبت
                
            self.table_all.setItem(row_idx, 3, status_item)
            
            self.table_all.setItem(row_idx, 4, QTableWidgetItem(time_str))

    def populate_absences_table(self, events, selected_worker_id):
        """الگوریتم پیشرفته محاسبه زمان غیبت‌ها بر اساس منطق درخواستی شما"""
        self.table_absences.setRowCount(0)
        
        # گروه‌بندی رخدادها بر اساس کارگر برای زمانی که گزینه «همه» انتخاب شده است
        from collections import defaultdict
        events_by_worker = defaultdict(list)
        for ev in events:
            events_by_worker[ev.get("employee_id")].append(ev)

        row_counter = 0

        for w_id, w_events in events_by_worker.items():
            worker_name = self.workers_map.get(w_id, f"کارگر {w_id}")
            pending_absent_time = None
            pending_camera_loc = "نامشخص"

            for ev in w_events:
                status_raw = (ev.get("event_type") or ev.get("status") or ev.get("type") or "").upper()
                time_raw = ev.get("timestamp", "")

                # الف) تشخیص ثبت رخداد غیبت (absent)
                if status_raw == "ABSENT":
                    try:
                        pending_absent_time = datetime.fromisoformat(time_raw.replace("Z", ""))
                        pending_camera_loc = self.cameras_map.get(ev.get("camera_id"), "لوکیشن نامشخص")
                    except:
                        pending_absent_time = None

                # ب) تشخیص ورود بعدی کارگر (enter یا IN)
                elif status_raw in ["ENTER", "IN"] and pending_absent_time is not None:
                    try:
                        enter_time = datetime.fromisoformat(time_raw.replace("Z", ""))
                        # محاسبه اختلاف زمان دقیق غیبت
                        duration = enter_time - pending_absent_time
                        
                        # تبدیل اختلاف زمان به فرمت قابل فهم (دقیقه و ثانیه)
                        total_seconds = int(duration.total_seconds())
                        minutes = total_seconds // 60
                        seconds = total_seconds % 60
                        duration_str = f"{minutes} دقیقه و {seconds} ثانیه"

                        # ثبت ردیف در جدول غیبت‌ها
                        self.table_absences.insertRow(row_counter)
                        self.table_absences.setItem(row_counter, 0, QTableWidgetItem(str(row_counter + 1)))
                        self.table_absences.setItem(row_counter, 1, QTableWidgetItem(worker_name))
                        self.table_absences.setItem(row_counter, 2, QTableWidgetItem(duration_str))
                        self.table_absences.setItem(row_counter, 3, QTableWidgetItem(str(pending_absent_time).split(".")[0]))
                        self.table_absences.setItem(row_counter, 4, QTableWidgetItem(pending_camera_loc))
                        
                        row_counter += 1
                    except Exception as ex:
                        print(f"Error parse time: {ex}")
                    
                    # ریست کردن وضعیت پندینگ برای غیبت بعدی کارگر
                    pending_absent_time = None

    # ---------------------------------------------------------
    # خروجی اکسل (Excel Export)
    # ---------------------------------------------------------
    def export_to_excel(self):
        active_table = self.table_all if self.current_view == "all" else self.table_absences
        if active_table.rowCount() == 0:
            QMessageBox.warning(self, "گزارش خالی", "هیچ داده‌ای برای خروجی گرفتن وجود ندارد.")
            return

        # خواندن عناوین هدر
        headers = [active_table.horizontalHeaderItem(i).text() for i in range(active_table.columnCount())]
        
        # استخراج داده‌های جدول فرانت
        row_data = []
        for row in range(active_table.rowCount()):
            current_row = []
            for col in range(active_table.columnCount()):
                item = active_table.item(row, col)
                current_row.append(item.text() if item else "")
            row_data.append(current_row)

        # ذخیره فایل با QFileDialog
        file_name, _ = QFileDialog.getSaveFileName(self, "ذخیره خروجی اکسل", "", "Excel Files (*.xlsx)")
        if file_name:
            if not file_name.endswith('.xlsx'):
                file_name += '.xlsx'
            try:
                df = pd.DataFrame(row_data, columns=headers)
                df.to_excel(file_name, index=False)
                QMessageBox.information(self, "موفقیت", "فایل اکسل گزارش با موفقیت ذخیره شد.")
            except Exception as e:
                QMessageBox.critical(self, "خطا", f"خطا در ذخیره فایل اکسل: {e}")

    # ---------------------------------------------------------
    # خروجی پی‌دی‌اف واقعی و تمیز (PDF Export)
    # ---------------------------------------------------------
    def export_to_pdf(self):
        active_table = self.table_all if self.current_view == "all" else self.table_absences
        if active_table.rowCount() == 0:
            QMessageBox.warning(self, "گزارش خالی", "هیچ داده‌ای برای خروجی گرفتن وجود ندارد.")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "ذخیره خروجی PDF", "", "PDF Files (*.pdf)")
        if file_name:
            if not file_name.endswith('.pdf'):
                file_name += '.pdf'
            
            # تولید یک بدنه HTML راست‌چین و شیک برای تبدیل به PDF بومی
            headers = [active_table.horizontalHeaderItem(i).text() for i in range(active_table.columnCount())]
            
            title_text = "گزارش جامع کلیه رخدادهای سیستم" if self.current_view == "all" else "گزارش تخصصی محاسبه غیبت‌های کارگران"
            
            html = f"""
            <div dir="rtl" style="font-family: Arial; padding: 20px;">
                <h2 style="text-align: center; color: #2c3e50;">{title_text}</h2>
                <p style="text-align: left; font-size: 12px; color: #7f8c8d;">تاریخ گزارش: {datetime.now().strftime('%Y-%m-%d  %H:%M')}</p>
                <table border="1" cellspacing="0" cellpadding="8" style="width: 100%; border-collapse: collapse; text-align: center;">
                    <tr style="background-color: #34495e; color: white; font-weight: bold;">
            """
            for h in headers:
                html += f"<th>{h}</th>"
            html += "</tr>"

            for row in range(active_table.rowCount()):
                html += "<tr>"
                for col in range(active_table.columnCount()):
                    item = active_table.item(row, col)
                    html += f"<td>{item.text() if item else ''}</td>"
                html += "</tr>"
            
            html += "</table></div>"

            # عملیات پرینت و ذخیره نهایی به PDF بومی ویندوز
            doc = QTextDocument()
            doc.setHtml(html)
            
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_name)
            
            doc.print_(printer)
            QMessageBox.information(self, "موفقیت", "فایل PDF گزارش با موفقیت ذخیره گردید.")