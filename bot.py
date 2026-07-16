import logging
import asyncio
import threading
from flask import Flask
from aiogram import Bot, Dispatcher
from config import TOKEN, PORT
from app.database.db import init_db
from app.handlers.user import user_router

# Loglarni sozlash (Xatolar va ishlash jarayonini ko'rsatib turadi)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Flask ilovasi (Render portni yopib qo'ymasligi va 24/7 ishlashi uchun)
app = Flask(__name__)

@app.route('/')
def index():
    return "Expense Tracker Bot is running 24/7! 🚀"

def run_flask():
    """Flask serverni alohida oqimda (thread) yurgizish"""
    app.run(host="0.0.0.0", port=PORT)

async def main():
    """Aiogram 3 botni ishga tushirish"""
    # 1. Baza jadvallarini yaratish (agar yo'q bo'lsa)
    init_db()
    logging.info("Ma'lumotlar bazasi tekshirildi va tayyor.")

    # 2. Bot va Dispatcher sozlamalari
    # Diqqat: .env dagi TOKEN olinadi (Xavfsizlik)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # 3. Routerlarni (handlerlarni) ulaymiz
    dp.include_router(user_router)

    # 4. Polling orqali botni yurgizish
    logging.info("Telegram bot ishga tushdi...")
    # Bot o'chib qolgan paytda kelgan xabarlarni o'tkazib yuborish
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Flask serverni orqa fonda ishga tushiramiz
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Aiogram botni asosiy oqimda ishga tushiramiz
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi.")
