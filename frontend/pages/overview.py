import requests
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# =======================================================
# کلاس پردازش پس‌زمینه برای دریافت اطلاعات از بک‌اند
# =======================================================
class DashboardDataThread(QThread):
    # تعریف سیگنال‌ها برای ارسال دیتای موفق یا پیام خطا به رابط کاربری
    data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            base_url = "http://localhost:8000"
            
            # ۱. دریافت کل کارگران
            # فرض بر این است که روت شما چیزی شبیه به این است
            emp_response = requests.get(f"{base_url}/employees/")
            emp_response.raise_for_status()
            employees = emp_response.json()
            total_workers = len(employees)

            # ۲. دریافت دوربین‌های فعال
            cam_response = requests.get(f"{base_url}/cameras/")
            cam_response.raise_for_status()
            cameras = cam_response.json()
            # اگر فیلد is_active دارید، می‌توانید اینجا فیلتر کنید، در غیر این صورت طول کل را می‌گیریم
            active_cameras = len([c for c in cameras if c.get("is_active", True)])

            # ۳. محاسبه کارگران غایب
            # این بخش بستگی به ساختار دقیق روتر attendance شما دارد.
            # فرض می‌کنیم روتر رخدادهای امروز را برمی‌گرداند.
            try:
                att_response = requests.get(f"{base_url}/attendance/") # آدرس دقیق روت تردد را اینجا قرار دهید
                if att_response.status_code == 200:
                    attendance_events = att_response.json()
                    # استخراج آیدی‌های یکتای کارگرانی که امروز حضور داشته‌اند
                    present_worker_ids = set([event.get("employee_id") for event in attendance_events])
                    absent_workers = len([aw for aw in attendance_events if aw.get("event_type") == "absent"])
                else:
                    absent_workers = 0
            except:
                absent_workers = 0 # اگر هنوز روت تردد کامل نشده، موقتا صفر می‌گذاریم

            # ارسال داده‌ها به رابط کاربری
            self.data_ready.emit({
                "total_workers": str(total_workers),
                "active_cameras": str(active_cameras),
                "absent_workers": str(absent_workers)
            })

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("خطا: سرور در دسترس نیست")
        except Exception as e:
            self.error_occurred.emit(f"خطا در دریافت داده: {str(e)}")

# =======================================================
# کلاس رابط کاربری صفحه نگاه کلی
# =======================================================
class OverviewPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # --- بخش بالایی: باکس‌های آماری ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # مقدار اولیه را "در حال لودینگ" می‌گذاریم تا به محض اجرای برنامه کاربر متوجه پروسه شود
        self.box_total_workers = self.create_stat_card("تعداد کل کارگران", "...")
        self.box_absent_workers = self.create_stat_card("کارگران غایب", "...")
        self.box_active_cameras = self.create_stat_card("دوربین‌های فعال", "...")

        top_layout.addWidget(self.box_total_workers)
        top_layout.addWidget(self.box_absent_workers)
        top_layout.addWidget(self.box_active_cameras)

        # --- بخش پایینی: نمودارها ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)

        chart1 = self.create_chart_placeholder("محل قرارگیری نمودار لحظه‌ای ۱")
        chart2 = self.create_chart_placeholder("محل قرارگیری نمودار لحظه‌ای ۲")

        bottom_layout.addWidget(chart1)
        bottom_layout.addWidget(chart2)

        layout.addLayout(top_layout, stretch=1)
        layout.addLayout(bottom_layout, stretch=3)

        # شروع فرآیند دریافت اطلاعات از بک‌اند به محض لود شدن صفحه
        self.fetch_data_from_backend()

    def create_stat_card(self, title, initial_value):
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        title_label.setAlignment(Qt.AlignCenter)

        value_label = QLabel(initial_value)
        value_label.setObjectName("CardValue")
        value_label.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    def create_chart_placeholder(self, text):
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)

        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #95a5a6; border: 2px dashed #bdc3c7; border-radius: 5px;")

        card_layout.addWidget(label)
        return card

    # --- متدهای مربوط به اتصال بک‌اند ---
    def fetch_data_from_backend(self):
        # ساخت و استارت Thread
        self.api_thread = DashboardDataThread()
        # متصل کردن سیگنال‌ها به توابع آپدیت رابط کاربری
        self.api_thread.data_ready.connect(self.update_stat_boxes)
        self.api_thread.error_occurred.connect(self.show_error)
        self.api_thread.start()

    def update_stat_boxes(self, data):
        # این تابع زمانی اجرا می‌شود که دیتای تمیز و آماده از Thread برسد
        self.box_total_workers.findChild(QLabel, "CardValue").setText(data["total_workers"])
        self.box_active_cameras.findChild(QLabel, "CardValue").setText(data["active_cameras"])
        self.box_absent_workers.findChild(QLabel, "CardValue").setText(data["absent_workers"])

    def show_error(self, error_msg):
        # نمایش پیغام خطا در باکس‌ها (مثلا اگر FastAPI خاموش باشد)
        self.box_total_workers.findChild(QLabel, "CardValue").setText("خطا")
        self.box_total_workers.findChild(QLabel, "CardValue").setStyleSheet("color: #e74c3c; font-size: 20px;")
        
        self.box_active_cameras.findChild(QLabel, "CardValue").setText("خطا")
        self.box_active_cameras.findChild(QLabel, "CardValue").setStyleSheet("color: #e74c3c; font-size: 20px;")
        
        self.box_absent_workers.findChild(QLabel, "CardValue").setText("خطا")
        self.box_absent_workers.findChild(QLabel, "CardValue").setStyleSheet("color: #e74c3c; font-size: 20px;")
        
        print(f"Backend Connection Error: {error_msg}")