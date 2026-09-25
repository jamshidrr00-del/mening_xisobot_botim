from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)
DB_NAME = 'database.db'

def get_db_connection():
    # timeout=10 parametri bot va web bir vaqtda baza bilan ishlaganda 'database locked' xatosini oldini oladi
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL,
            description TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Dastur ishga tushganda baza jadvalini tekshirish
init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, amount, description FROM transactions ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', transactions=rows)

@app.route('/add', methods=['POST'])
def add_transaction():
    trans_type = request.form.get('type')
    amount = request.form.get('amount')
    description = request.form.get('description')
    
    if amount and description:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transactions (type, amount, description) VALUES (?, ?, ?)", 
                (trans_type, float(amount), description)
            )
            conn.commit()
            conn.close()
        except ValueError:
            pass  # Raqam emas matn kiritilsa xatolik bermasligi uchun
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
