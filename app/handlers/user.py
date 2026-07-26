import logging
import sqlite3
from datetime import datetime
import pytz
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from app.keyboards.reply import get_main_menu, get_settings_menu
from app.services.parser import parse_expense_text
from config import DB_PATH, TIMEZONE

user_router = Router()

@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    full_name = message.from_user.full_name
    await message.answer(
        f"Salom, {full_name}! 👋\n\n"
        f"Men sizning shaxsiy moliyaviy yordamchingizman.\n"
        f"Xarajat kiritish uchun shunchaki matn yozing (Masalan: `Non 18000`, `2 ta non 36000` yoki `Taxi 30000`).",
        reply_markup=get_main_menu()
    )

@user_router.message(F.text == "⚙️ Sozlamalar")
async def process_settings(message: types.Message):
    await message.answer("⚙️ Sozlamalar bo'limidasiz. Nima o'zgartiramiz?", reply_markup=get_settings_menu())

@user_router.message(F.text == "⬅️ Ortga")
async def process_back(message: types.Message):
    await message.answer("Asosiy menyuga qaytdik 🏠", reply_markup=get_main_menu())

# FOYDALANUVCHI XARAJAT YOZGANDA ISHLAYDIGAN ASOSIY FUNKSIYA
@user_router.message(F.text)
async def process_expense_input(message: types.Message):
    text = message.text.strip()
    
    # Boshqa menyu tugmalarini vaqtincha bloklash
    ignore_list = ["➕ Xarajat", "📊 Hisobot", "📆 Haftalik", "📅 Oylik", "📂 Arxiv"]
    if text in ignore_list:
        await message.answer(f"Hozircha *{text}* bo'limi tayyorlanmoqda 🛠", parse_mode="Markdown")
        return

    # 1. Matnni xizmat orqali aqlli tahlil qilish
    parsed_data = parse_expense_text(text)
    
    if not parsed_data:
        await message.answer("⚠️ Iltimos, xarajat summasini raqamda kiriting.\nMasalan: `Non 18000` yoki `Taxi 30000`")
        return
        
    item_name = parsed_data['item_name']
    amount = parsed_data['amount']
    category = parsed_data['category']
    
    # 2. Vaqt va sanani olish (Toshkent vaqti bilan)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    
    # 3. Ma'lumotni Bazaga xavfsiz saqlash
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, item_name, category, date, time) VALUES (?, ?, ?, ?, ?, ?)",
        (message.from_user.id, amount, item_name, category, current_date, current_time)
    )
    conn.commit()
    conn.close()
    
    # 4. Foydalanuvchiga chiroyli tasdiq yuborish
    await message.answer(
        f"✅ **Xarajat saqlandi!**\n\n"
        f"📝 Nomi: {item_name}\n"
        f"💰 Summa: {amount:,} so'm\n"
        f"🗂 Kategoriya: {category}\n"
        f"📅 Vaqt: {current_date} {current_time}",
        parse_mode="Markdown"
    )
