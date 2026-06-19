from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QPushButton, QMessageBox, QGroupBox, QLabel)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QIntValidator # 🔴 ایمپورت محدودکننده اعداد

class SettingsPage(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.settings = QSettings("SmartVision", "AttendanceSystem")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("⚙️ تنظیمات و شخصی‌سازی سیستم")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        # ==========================================
        # بخش ۱: تنظیمات عناوین و کلمات (Terminology)
        # ==========================================
        term_group = QGroupBox("تنظیمات کلمات و عناوین نمایشی")
        term_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2980b9; font-size: 14px; border: 1px solid #bdc3c7; padding: 15px; margin-top: 10px;}")
        term_layout = QFormLayout(term_group)
        term_layout.setSpacing(15)

        self.inp_singular = QLineEdit()
        self.inp_singular.setText(self.settings.value("term_singular", "کارگر"))
        self.inp_singular.setFixedWidth(250)

        self.inp_plural = QLineEdit()
        self.inp_plural.setText(self.settings.value("term_plural", "کارگران"))
        self.inp_plural.setFixedWidth(250)

        term_layout.addRow("کلمه مفرد (مثلاً کارمند، دانش‌آموز):", self.inp_singular)
        term_layout.addRow("کلمه جمع (مثلاً کارمندان، دانش‌آموزان):", self.inp_plural)
        
        lbl_notice = QLabel("⚠️ توجه: بعد از تغییر کلمات باید برنامه را بسته و از اول اجرا کنید.")
        lbl_notice.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 11px; margin-top: 5px;")
        term_layout.addRow("", lbl_notice)
        
        layout.addWidget(term_group)

        # ==========================================
        # بخش ۲: تنظیمات ترشولد غیبت‌ها (Thresholds)
        # ==========================================
        thresh_group = QGroupBox("تنظیمات تحلیل رفتار و غیبت‌ها")
        thresh_group.setStyleSheet("QGroupBox { font-weight: bold; color: #e67e22; font-size: 14px; border: 1px solid #bdc3c7; padding: 15px; margin-top: 10px;}")
        thresh_layout = QFormLayout(thresh_group)
        thresh_layout.setSpacing(15)

        # 🔴 استفاده از تکست‌باکس با قابلیت تایپ و اعمال Validator برای اعداد
        self.inp_ignore = QLineEdit()
        self.inp_ignore.setValidator(QIntValidator(0, 9999)) # فقط اجازه تایپ عدد
        self.inp_ignore.setFixedWidth(150)
        self.inp_ignore.setAlignment(Qt.AlignCenter)
        self.inp_ignore.setText(str(self.settings.value("thresh_ignore", 2)))

        self.inp_danger = QLineEdit()
        self.inp_danger.setValidator(QIntValidator(1, 9999)) # فقط اجازه تایپ عدد
        self.inp_danger.setFixedWidth(150)
        self.inp_danger.setAlignment(Qt.AlignCenter)
        self.inp_danger.setText(str(self.settings.value("thresh_danger", 15)))

        # 🔴 تغییر متون راهنما
        thresh_layout.addRow("حذف نویز (غیبت‌های زیر این زمان ثبت نمی‌شوند) - بر حسب دقیقه:", self.inp_ignore)
        thresh_layout.addRow("مرز خطر (غیبت‌های بالای این زمان قرمز می‌شوند) - بر حسب دقیقه:", self.inp_danger)
        
        layout.addWidget(thresh_group)

        # ==========================================
        # دکمه ذخیره
        # ==========================================
        btn_save = QPushButton("💾 ذخیره تغییرات و اعمال در سیستم")
        btn_save.setStyleSheet("background-color: #2ecc71; color: white; font-size: 15px; font-weight: bold; padding: 12px; border-radius: 5px; max-width: 300px;")
        btn_save.clicked.connect(self.save_settings)

        layout.addSpacing(20)
        layout.addWidget(btn_save, alignment=Qt.AlignCenter)
        layout.addStretch()

    def save_settings(self):
        self.settings.setValue("term_singular", self.inp_singular.text().strip())
        self.settings.setValue("term_plural", self.inp_plural.text().strip())
        
        # 🔴 خواندن مقادیر تایپ شده و جلوگیری از خطای خالی بودن باکس‌ها
        ignore_val = self.inp_ignore.text().strip()
        danger_val = self.inp_danger.text().strip()
        
        self.settings.setValue("thresh_ignore", int(ignore_val) if ignore_val else 2)
        self.settings.setValue("thresh_danger", int(danger_val) if danger_val else 15)

        QMessageBox.information(self, "موفقیت", "تغییرات با موفقیت ذخیره شد.")
        self.settings_changed.emit()