import sqlite3
import os

# Ma'lumotlar bazasi fayli nomi
DB_PATH = 'bot_database.db'

def get_connection():
    """Ma'lumotlar bazasiga ulanishni yaratish."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Barcha kerakli jadvallarni noldan yaratish."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Foydalanuvchilar va ularning plastik karta balansi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Xarajat kategoriyalari (Masalan: Oziq-ovqat, Transport va hk)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # 3. Xarajatlar tarixi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            category_id INTEGER,
            item_name TEXT,
            date TEXT,
            time TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# ==========================================
# FOYDALANUVCHILAR VA BALANS FUNKSIYALARI
# ==========================================

def add_user(user_id, initial_balance=0.0):
    """Yangi foydalanuvchini bazaga qo'shish."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, balance) 
        VALUES (?, ?)
    ''', (user_id, initial_balance))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    """Foydalanuvchi balansiga mablag' qo'shish yoki tahrirlash."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET balance = balance + ? WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    """Foydalanuvchining joriy balansini olish."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0.0

# ==========================================
# KATEGORIYALAR FUNKSIYALARI
# ==========================================

def add_category(name):
    """Yangi xarajat kategoriyasini qo'shish."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Kategoriya allaqachon mavjud bo'lsa, xato bermasdan davom etadi
    conn.close()

def get_categories():
    """Barcha kategoriyalarni ro'yxat sifatida olish."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories')
    results = cursor.fetchall()
    conn.close()
    return results

# ==========================================
# XARAJATLAR FUNKSIYALARI
# ==========================================

def add_expense(user_id, amount, category_id, item_name, date, time):
    """Xarajatni bazaga qo'shish va uni ro'yxatdan o'tkazish."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Xarajatni bazaga yozish
    cursor.execute('''
        INSERT INTO expenses (user_id, amount, category_id, item_name, date, time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, category_id, item_name, date, time))
    
    # 2. Xarajat qilingan summani foydalanuvchi joriy balansidan ayirib tashlash
    cursor.execute('''
        UPDATE users SET balance = balance - ? WHERE user_id = ?
    ''', (amount, user_id))
    
    conn.commit()
    conn.close()

def get_expenses(user_id, limit=10):
    """Foydalanuvchining oxirgi xarajatlarini batafsil ro'yxat sifatida olish."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.id, e.amount, c.name, e.item_name, e.date, e.time 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ?
        ORDER BY e.id DESC
        LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results

def get_total_expenses(user_id):
    """Jami qilingan xarajatlar summasini hisoblash."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(amount) FROM expenses WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result[0] else 0.0
