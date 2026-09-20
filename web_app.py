from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)

# Bazaga ulanish funksiyasi (botingiz ishlatadigan bazaga moslab nomini o'zgartirishingiz mumkin)
def init_db():
    conn = sqlite3.connect('database.db')
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

init_db()

@app.route('/')
index():
    # Bazadan oxirgi yozuvlarni o'qib chiqish
    conn = sqlite3.connect('database.db')
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
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (type, amount, description) VALUES (?, ?, ?)", 
                       (trans_type, float(amount), description))
        conn.commit()
        conn.close()
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
