import os
import sqlite3
import logging
import asyncio
import re
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
    # Asosiy jadval
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            item_name TEXT,
            category TEXT,
            date TEXT,
            is_closed INTEGER DEFAULT 0
        )
    ''')
    # Agar eski bazada 'item_name' ustuni bo'lmasa, uni qo'shish (Xatolik bermasligi uchun)
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN item_name TEXT")
    except sqlite3.OperationalError:
        pass  # Ustun allaqachon mavjud bo'lsa, o'tib ketadi
        
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
    await message.answer("Salom! Men sizning yangilangan aqlli Kunlik Xarajatlar botingizman.\n\n"
                         "📝 Xarajatlarni kiritish uchun masalan:\n"
                         "`olma 5000` yoki `benzin 55000` deb yozib yuboring.\n\n"
                         "📊 Qo'lda hisobot olish uchun: /hisobot")

# Xabar kelganda matn va raqamni ajratib olish
@dp.message(F.text)
async def process_expense_input(message: types.Message):
    if message.from_user.id != USER_ID:
        return

    text = message.text.strip()
    
    # Buyruqlarni o'tkazib yuborish
    if text.startswith('/'):
        return

    # Matn ichidan barcha raqamlarni qidirish
    numbers = re.findall(r'\d+', text)

    if not numbers:
        await message.answer("Iltimos, xarajat summasini raqamda kiriting.\nMasalan: `olma 5000` yoki shunchaki `5000`")
        return

    # Oxirgi topilgan raqamni summa deb olamiz (masalan, "olma 5000" -> 5000)
    amount = int(numbers[-1])
    
    # Raqamni olib tashlab, qolgan matnni xarajat nomi deb olamiz
    item_name = text.replace(str(amount), "").strip()
    if not item_name:
        item_name = "Xarajat"

    current_date = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")

    # Ma'lumotni vaqtinchalik 'DRAFT' holatida saqlaymiz
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, item_name, category, date) VALUES (?, ?, ?, ?, ?)",
        (message.from_user.id, amount, item_name, "DRAFT", current_date)
    )
    draft_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Kategoriya tanlash tugmalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"set_{draft_id}_{key}")]
        for key, name in CATEGORIES.items()
    ])

    await message.answer(
        f"📝 *Xarajat:* {item_name}\n"
        f"💰 *Summa:* {amount:,} so'm\n\n"
        f"Ushbu xarajat uchun kategoriya tanlang:", 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

# Kategoriya tanlanganda bazani yangilash
@dp.callback_query(F.data.startswith("set_"))
async def save_expense_category(callback: types.CallbackQuery):
    _, draft_id, cat_key = callback.data.split("_")
    category_name = CATEGORIES[cat_key]

    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    # Loyiha tafsilotlarini bazadan o'qiymiz
    cursor.execute("SELECT amount, item_name, date FROM expenses WHERE id = ?", (draft_id,))
    row = cursor.fetchone()
    
    if row:
        amount, item_name, current_date = row
        # 'DRAFT'ni haqiqiy kategoriyaga o'zgartiramiz
        cursor.execute("UPDATE expenses SET category = ? WHERE id = ?", (category_name, draft_id))
        conn.commit()
        
        await callback.message.edit_text(
            f"✅ **Saqlandi!**\n\n"
            f"📅 Sana: {current_date}\n"
            f"📝 Nomi: {item_name}\n"
            f"🗂 Kategoriya: {category_name}\n"
            f"💰 Summa: {amount:,} so'm",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text("❌ Xatolik: Ma'lumot topilmadi.")
        
    conn.close()
    await callback.answer()

# Hisobot matnini chiroyli guruhlab tayyorlash funksiyasi
def generate_report_text(date_str):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    # Tasdiqlangan xarajatlarni olish (DRAFT bo'lmaganlarini)
    cursor.execute(
        "SELECT category, item_name, amount FROM expenses WHERE date = ? AND category != 'DRAFT'",
        (date_str,)
    )
    rows = cursor.fetchall()

    # Umumiy summani hisoblash
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE date = ? AND category != 'DRAFT'",
        (date_str,)
    )
    total = cursor.fetchone()[0] or 0
    conn.close()

    if total == 0:
        return f"📅 {date_str} kuni hech qanday xarajat kiritilmadi. 🤝"

    # Kategoriyalar bo'yicha guruhlash (Python orqali)
    grouped = {}
    for cat, item, amt in rows:
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append((item, amt))

    # Hisobot matnini yig'ish
    report = f"📊 **Kunlik Xarajatlar Hisoboti**\n📅 Sana: {date_str}\n"
    report += "-----------------------------\n"
    
    for cat, items in grouped.items():
        report += f"\n{cat}:\n"
        for item, amt in items:
            report += f" • {item} — {amt:,} so'm\n"
            
    report += "-----------------------------\n"
    report += f"💰 **JAMI:** {total:,} so'm"
    return report

# Qo'lda hisobot so'ralganda
@dp.message(Command("hisobot"))
async def cmd_report(message: types.Message):
    if message.from_user.id != USER_ID:
        return
    current_date = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
    report_text = generate_report_text(current_date)
    await message.answer(report_text, parse_mode="Markdown")

# Har kuni soat 22:00 da avtomatik ishlaydigan va kunni yopadigan funksiya
async def auto_daily_report():
    current_date = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")

    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    # Yopilmagan va tasdiqlangan xarajatlar bormi tekshiramiz
    cursor.execute(
        "SELECT COUNT(*) FROM expenses WHERE date = ? AND is_closed = 0 AND category != 'DRAFT'",
        (current_date,)
    )
    open_expenses = cursor.fetchone()[0]

    if open_expenses > 0:
        # Hisobot tayyorlab yuborish
        report_text = "⏰ **Soat 22:00 bo'ldi! Kunlik avtomat hisobot:**\n\n" + generate_report_text(current_date)
        try:
            await bot.send_message(chat_id=USER_ID, text=report_text, parse_mode="Markdown")
            # Kunni yopilgan deb belgilaymiz
            cursor.execute(
                "UPDATE expenses SET is_closed = 1 WHERE date = ? AND category != 'DRAFT'",
                (current_date,)
            )
            # Tasdiqlanmay chala qolib ketgan "DRAFT" xarajatlarni tozalaymiz
            cursor.execute("DELETE FROM expenses WHERE category = 'DRAFT'")
            conn.commit()
        except Exception as e:
            logging.error(f"Avtomat hisobot yuborishda xato: {e}")
            
    conn.close()

# Botni ishga tushirish
async def main():
    # Taymerni sozlash (Har kuni 22:00 da)
    scheduler.add_job(auto_daily_report, 'cron', hour=22, minute=0, timezone=TASHKENT_TZ)
    scheduler.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
