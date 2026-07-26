import logging
import asyncio
import threading
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import TOKEN, PORT
from app.database.db import init_db
from app.handlers.user import user_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/')
def index():
    return "Expense Tracker Bot is running 24/7! 🚀"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# BOT BUYRUQLAR MENYUSINI SOZLASH (O'ZBEK TILIDA)
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish 🚀"),
        BotCommand(command="report", description="Bugungi hisobot 📊"),
        BotCommand(command="weekly", description="Haftalik hisobot 📆"),
        BotCommand(command="monthly", description="Oylik hisobot 📅"),
        BotCommand(command="undo", description="Oxirgi xarajatni o'chirish 🗑"),
        BotCommand(command="settings", description="Sozlamalar ⚙️")
    ]
    await bot.set_my_commands(commands)

async def main():
    init_db()
    logging.info("Ma'lumotlar bazasi tekshirildi va tayyor.")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(user_router)

    # Buyruqlar menyusini yuklaymiz
    await set_bot_commands(bot)

    logging.info("Telegram bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi.")
