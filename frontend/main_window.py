from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget, QLabel
from PyQt5.QtCore import Qt
import os

# ایمپورت صفحات ساخته شده
from pages.overview import OverviewPage
from pages.live_dashboard import LiveDashboardPage
from pages.workers_list import WorkersListPage
from pages.events import EventsPage
from pages.add_worker import AddWorkerPage
from pages.cameras import CamerasPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("سیستم هوشمند حضور و غیاب")
        self.resize(1100, 700)
        
        # ویجت مرکزی و لایوت اصلی افقی
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # ۱. بخش سایدبار (منوی کناری)
        # ---------------------------------------------------------
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        sidebar_layout.setSpacing(8)
        sidebar_layout.setAlignment(Qt.AlignTop)

        # دکمه‌های منوی اصلی
        self.btn_overview = QPushButton("نگاه کلی")
        self.btn_overview.setObjectName("MenuButton")

        self.btn_live = QPushButton("داشبورد زنده")
        self.btn_live.setObjectName("MenuButton")

        # --- منوی کشویی کارگران ---
        self.btn_workers_parent = QPushButton("کارگران ▼")
        self.btn_workers_parent.setObjectName("ParentMenuButton")
        self.btn_workers_parent.clicked.connect(self.toggle_workers_menu)

        # کانتینر زیرمنو (شامل گزینه‌های کشویی)
        self.workers_sub_container = QWidget()
        self.workers_sub_container.setObjectName("SubMenuContainer")
        sub_layout = QVBoxLayout(self.workers_sub_container)
        sub_layout.setContentsMargins(15, 0, 0, 0) # کمی جلوتر آمدن زیرمنوها نسبت به منوی اصلی
        sub_layout.setSpacing(5)

        self.btn_workers_list = QPushButton("• لیست کارگران")
        self.btn_workers_list.setObjectName("SubMenuButton")
        self.btn_add_worker = QPushButton("• افزودن کارگر")
        self.btn_add_worker.setObjectName("SubMenuButton")

        sub_layout.addWidget(self.btn_workers_list)
        sub_layout.addWidget(self.btn_add_worker)
        
        # به صورت پیش‌فرض منوی کشویی بسته باشد
        self.workers_sub_container.setVisible(False)
        # ---------------------------

        self.btn_events = QPushButton("رخدادها")
        self.btn_events.setObjectName("MenuButton")

        self.btn_cameras = QPushButton("دوربین‌ها")
        self.btn_cameras.setObjectName("MenuButton")

        self.btn_settings = QPushButton("تنظیمات")
        self.btn_settings.setObjectName("MenuButton")

        # اضافه کردن دکمه‌ها به لایوت سایدبار
        sidebar_layout.addWidget(self.btn_overview)
        sidebar_layout.addWidget(self.btn_live)
        sidebar_layout.addWidget(self.btn_workers_parent)
        sidebar_layout.addWidget(self.workers_sub_container) # کانتینر کشویی اینجا قرار می‌گیرد
        sidebar_layout.addWidget(self.btn_events)
        sidebar_layout.addWidget(self.btn_cameras)
        sidebar_layout.addWidget(self.btn_settings)

        # ---------------------------------------------------------
        # ۲. بخش نمایش صفحات (Stacked Widget)
        # ---------------------------------------------------------
        self.page_container = QStackedWidget()
        
        # تعریف صفحات واقعی و دمی
        self.page_overview = OverviewPage()
        self.page_live = LiveDashboardPage()
        self.page_workers_list = WorkersListPage()
        self.page_add_worker = AddWorkerPage()
        self.page_events = EventsPage()
        self.page_cameras = CamerasPage()
        self.page_settings = self.create_dummy_page("صفحه تنظیمات")

        # اضافه کردن صفحات به کانتینر مرکزی با ایندکس مشخص
        self.page_container.addWidget(self.page_overview)      # Index 0
        self.page_container.addWidget(self.page_live)          # Index 1
        self.page_container.addWidget(self.page_workers_list)   # Index 2
        self.page_container.addWidget(self.page_add_worker) # Index 3
        self.page_container.addWidget(self.page_events)        # Index 4
        self.page_container.addWidget(self.page_cameras)       # Index 5
        self.page_container.addWidget(self.page_settings)      # Index 6

        # متصل کردن کلیک دکمه‌ها به تغییر صفحات
        self.btn_overview.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_overview))
        self.btn_live.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_live))
        self.btn_workers_list.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_workers_list))
        self.btn_add_worker.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_add_worker))
        self.btn_events.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_events))
        self.btn_cameras.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_cameras))
        self.btn_settings.clicked.connect(lambda: self.page_container.setCurrentWidget(self.page_settings))

        self.page_workers_list.switch_to_add_worker.connect(
            lambda: self.page_container.setCurrentWidget(self.page_add_worker)
        )

        # افزودن سایدبار و کانتینر صفحات به لایوت اصلی نرم‌افزار
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.page_container, stretch=1)

    def toggle_workers_menu(self):
        """تابع باز و بسته کردن منوی کشویی کارگران"""
        is_visible = self.workers_sub_container.isVisible()
        self.workers_sub_container.setVisible(not is_visible)
        
        # تغییر فلش دکمه برای زیبایی بصری
        if is_visible:
            self.btn_workers_parent.setText("کارگران ▼")
        else:
            self.btn_workers_parent.setText("کارگران ▲")

    def create_dummy_page(self, text):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: #7f8c8d;")
        layout.addWidget(label)
        return widget