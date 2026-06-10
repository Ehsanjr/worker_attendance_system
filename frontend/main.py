import sys
import os
from pathlib import Path

# ۱. محاسبه دقیق مسیرهای پروژه
BASE_DIR = Path(__file__).resolve().parent.parent
AI_DIR = BASE_DIR / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.append(str(AI_DIR))

# ۲. *** کلید حل مشکل ویندوز: ایمپورت ONNX قبل از PyQt ***
# این کار باعث می‌شود DLLهای مربوط به CUDA و شتاب‌دهنده گرافیکی
# قبل از کتابخانه‌های بصری Qt در حافظه لود شوند و با هم تداخل نکنند.
import onnxruntime

# ۳. حالا ایمپورت‌های PyQt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from main_window import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # راست‌چین کردن کل رابط کاربری
    app.setLayoutDirection(Qt.RightToLeft)

    # پیدا کردن مسیر دقیق فایل استایل و خواندن آن
    style_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"اخطار: فایل استایل در مسیر زیر پیدا نشد!\n{style_path}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())