import sqlite3
import os
from config import DB_PATH

def get_db_connection():
    """Ma'lumotlar bazasiga xavfsiz ulanish yaratish"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Natijalarni dict ko'rinishida olish uchun
    return conn

def init_db():
    """Barcha jadvallarni TZ bo'yicha yaratish"""
    # data papkasi mavjudligini tekshirish
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            language TEXT DEFAULT 'uz',
            created_at TEXT,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    
    # 2. Kategoriyalar jadvali (Har bir user uchun alohida)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Xarajatlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            item_name TEXT,
            category TEXT,
            date TEXT,
            time TEXT,
            is_closed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
        )
    ''')
    
    # 4. Tizim loglari jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            timestamp TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
