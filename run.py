import asyncio
import logging
import os
import threading
import sqlite3
from aiogram import Bot, Dispatcher, types
from flask import Flask, render_template, request, redirect, url_for

# Tokenni .env yoki to'g'ridan-to'g'ri yozishingiz mumkin
TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ") 
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FLASK WEBBING (Mini App) ---
app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
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

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # Render portni darhol ko'rishi uchun host='0.0.0.0' shart
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- AIOGRAM BOT HANDLERS ---
@dp.message(lambda message: message.text == '/start')
async def start_cmd(message: types.Message):
    await message.answer("Assalomu alaykum! Toyxona hisobot botiga xush kelibsiz.")

async def main():
    # Eski osilib qolgan getUpdates so'rovlarini tozalash (Konfliktni oldini oladi)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot polling boshlandi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    # 1. Flask serverini alohida background thread'da ishga tushiramiz (Port ochiladi)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 2. Bot polling'ni asosiy oqimda ishga tushiramiz
    asyncio.run(main())
