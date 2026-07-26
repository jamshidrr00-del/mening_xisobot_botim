import os
import sqlite3
import logging
import asyncio
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

# Bot tokeni (Render'dagi Environment Variables'dan olinadi)
TOKEN = os.getenv("TOKEN")

# DIQQAT: Quyidagi 12345678 o'rniga o'zingizning haqiqiy Telegram ID raqamingizni yozing!
USER_ID = 1002593949  

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Toshkent vaqt zonasi
TASHKENT_TZ = pytz.timezone('Asia/Tashkent')

# Ma'lumotlar bazasini sozlash (SQLite)
def init_db():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            category TEXT,
            date TEXT,
            is_closed INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Kategoriyalar ro'yxati
CATEGORIES = {
    "food": "🍔 Ovqat",
    "transport": "🚕 Yo'l",
    "market": "🛒 Bozorlik",
    "utilities": "💡 Kommunal",
    "other": "🎁 Boshqa"
}

# Start buyrug'i
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != USER_ID:
        return
    await message.answer("Salom! Men sizning Kunlik Xarajatlar botingizman.\n"
                         "Xarajat kiritish uchun shunchaki summani raqamda yuboring.\n"
                         "Hisobot olish uchun /hisobot buyrug'ini bosing.")

# Xarajat miqdori yuborilganda kategoriyani so'rash
@dp.message(F.text.regexp(r'^\d+$'))
async def process_amount(message: types.Message):
    if message.from_user.id != USER_ID:
        return
    
    amount = int(message.text)
    
    # Kategoriya tanlash uchun tugmalar (Inline Buttons)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"exp_{amount}_{key}")]
        for key, name in CATEGORIES.items()
    ])
    
    await message.answer(f"💰 {amount:,} so'm xarajat uchun kategoriya tanlang:", reply_markup=keyboard)

# Kategoriya bosilganda bazaga saqlash
@dp.callback_query(F.data.startswith("exp_"))
async def save_expense(callback: types.CallbackQuery):
    _, amount, cat_key = callback.data.split("_")
    category_name = CATEGORIES[cat_key]
    current_date = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
        (callback.from_user.id, int(amount), category_name, current_date)
    )
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(f"✅ Saqlandi:\n📅 Sana: {current_date}\n🗂 Kategoriya: {category_name}\n💰 Summa: {int(amount):,} so'm")
    await callback.answer()

# Hisobot tayyorlash funksiyasi
def generate_report_text(date_str):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    # Kategoriyalar bo'yicha guruhlash
    cursor.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE date = ? GROUP BY category", 
        (date_str,)
    )
    rows = cursor.fetchall()
    
    # Umumiy summani hisoblash
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE date = ?", (date_str,))
    total = cursor.fetchone()[0] or 0
    
    conn.close()
    
    if total == 0:
        return f"📅 {date_str} kuni hech qanday xarajat qilinmadi. 🤝"
        
    report = f"📊 **Kunlik Xarajatlar Hisoboti**\n📅 Sana: {date_str}\n"
    report += "-----------------------------\n"
    for row in rows:
        report += f"{row[0]}: {row[1]:,} so'm\n"
    report += "-----------------------------\n"
    report += f"💰 **JAMI:** {total:,} so'm"
    return report

# Hisobot buyrug'i (Qo'lda so'ralganda)
@dp.message(Command("hisobot"))
async def cmd_report(message: types.Message):
    if message.from_user.id != USER_ID:
        return
    current_date = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
    report_text = generate_report_text(current_date)
    await message.answer(report_text, parse_mode="Markdown")

# Soat 22:00 da avtomatik ishlaydigan funksiya
async def auto_daily_report():
    current_date = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    # Kun yopilgan yoki yopilmaganini tekshirish
    cursor.execute("SELECT COUNT(*) FROM expenses WHERE date = ? AND is_closed = 0", (current_date,))
    open_expenses = cursor.fetchone()[0]
    
    if open_expenses > 0:
        # Hisobot matnini tayyorlash
        report_text = "⏰ **Soat 22:00 bo'ldi! Kunlik avtomat hisobot:**\n\n" + generate_report_text(current_date)
        
        # Foydalanuvchiga yuborish
        try:
            await bot.send_message(chat_id=USER_ID, text=report_text, parse_mode="Markdown")
            # Kunni yopilgan deb belgilash
            cursor.execute("UPDATE expenses SET is_closed = 1 WHERE date = ?", (current_date,))
            conn.commit()
        except Exception as e:
            logging.error(f"Avtomat hisobot yuborishda xato: {e}")
            
    conn.close()

# Bot ishga tushganda tahrirlarni sozlash
async def main():
    # Har kuni soat 22:00 da avtomat hisobot yuborish taymeri
    scheduler.add_job(auto_daily_report, 'cron', hour=22, minute=0, timezone=TASHKENT_TZ)
    scheduler.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
