import sqlite3
from pathlib import Path

# ۱. پیدا کردن مسیر دقیق فایل دیتابیس فعلی شما
DB_PATH = Path(__file__).resolve().parent.parent / "attendance.db"

def upgrade_and_update_employees():
    if not DB_PATH.exists():
        print(f"❌ خطا: فایل دیتابیس در مسیر زیر پیدا نشد:\n{DB_PATH}")
        return

    # اتصال مستقیم به دیتابیس SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("⏳ در حال ارتقای ساختار جدول کارگران...")

    # ۲. اضافه کردن ستون کد ملی (national_id) به صورت متن و قابلیت Null بودن
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN national_id TEXT;")
        print("✅ ستون national_id با موفقیت به جدول اضافه شد.")
    except sqlite3.OperationalError:
        # این بخش ملو برای زمانی است که ستون از قبل وجود داشته باشد تا برنامه کرش نکند
        print("ℹ️ ستون national_id از قبل در دیتابیس وجود دارد.")

    # ۳. اضافه کردن ستون تلفن همراه (phone_number)
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN phone_number TEXT;")
        print("✅ ستون phone_number با موفقیت به جدول اضافه شد.")
    except sqlite3.OperationalError:
        print("ℹ️ ستون phone_number از قبل در دیتابیس وجود دارد.")

    # ۴. به‌روزرسانی اطلاعات ۳ کارگر موجود بر اساس نام آن‌ها
    fake_data = {
        "ehsan": {"national_id": "1270000001", "phone_number": "09120000001"},
        "hosein": {"national_id": "1270000002", "phone_number": "09120000002"},
        "amirhosein": {"national_id": "1270000003", "phone_number": "09120000003"}
    }

    print("\n⏳ در حال تزریق اطلاعات جدید به کارگران قدیمی...")
    
    for name, data in fake_data.items():
        # بررسی اینکه آیا کارگری با این نام وجود دارد یا خیر
        cursor.execute("SELECT id FROM employees WHERE name = ?;", (name,))
        result = cursor.fetchone()
        
        if result:
            cursor.execute("""
                UPDATE employees 
                SET national_id = ?, phone_number = ? 
                WHERE name = ?;
            """, (data["national_id"], data["phone_number"], name))
            print(f"   🔹 اطلاعات تکمیلی کارگر '{name}' با موفقیت ست شد.")
        else:
            print(f"   ⚠️ کارگری با نام '{name}' در دیتابیس یافت نشد تا آپدیت شود.")

    # ذخیره نهایی تغییرات و بستن اتصال
    conn.commit()
    conn.close()
    print("\n✅ عملیات جراحی دیتابیس با موفقیت به پایان رسید. تمام داده‌های قبلی حفظ شدند.")

if __name__ == "__main__":
    upgrade_and_update_employees()