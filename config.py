import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Bot sozlamalari
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Web Server sozlamalari (Render uchun)
PORT = int(os.getenv("PORT", 5000))

# Vaqt zonasi
TIMEZONE = "Asia/Tashkent"

# Ma'lumotlar bazasi yo'li
DB_PATH = os.path.join("data", "expense_tracker.db")
