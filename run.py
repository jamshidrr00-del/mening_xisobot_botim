import asyncio
import logging
import os
import threading
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from flask import Flask, render_template, request, redirect, url_for

# Logging sozlamasi
logging.basicConfig(level=logging.INFO)

# Tokenni Render muhitidan o'qiydi
TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ") 
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ==================== FLASK (WEB SERVER / MINI APP) QISMI ====================
app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT type, amount, description FROM transactions ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
    except Exception:
        rows = []
    return render_template('index.html', transactions=rows)

@app.route('/add', methods=['POST'])
def add_transaction():
    trans_type = request.form.get('type')
    amount = request.form.get('amount')
    description = request.form.get('description')
    
    if amount and description:
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (type, amount, description) VALUES (?, ?, ?)", 
                           (trans_type, float(amount), description))
            conn.commit()
            conn.close()
        except Exception as e:
            print("DB Error:", e)
            
    return redirect(url_for('index'))

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ==================== AIOGRAM BOT QISMI ====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Assalomu alaykum! To'yxona hisobot botiga xush kelibsiz.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot polling muvaffaqiyatli boshlandi...")
    await dp.start_polling(bot)


# ==================== ASOSIY ISHGA TUSHIRISH ====================
if __name__ == '__main__':
    # 1. Flask serverini alohida background thread'da ishga tushiramiz (Port ochiladi)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 2. Bot polling'ni asosiy oqimda ishga tushiramiz
    asyncio.run(main())
