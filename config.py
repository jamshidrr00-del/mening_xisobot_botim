import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Bot sozlamalari
TOKEN = os.getenv("8522306001:AAFNLspuu9QEX0wCGvzohK69Bf2qietscXQ")
ADMIN_ID = int(os.getenv("1002593949", 0))

# Web Server sozlamalari (Render uchun)
PORT = int(os.getenv("PORT", 5000))

# Vaqt zonasi
TIMEZONE = "Asia/Tashkent"

# Ma'lumotlar bazasi yo'li
DB_PATH = os.path.join("data", "expense_tracker.db")
