import logging
import sqlite3
from datetime import datetime
import pytz
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from app.keyboards.reply import get_settings_menu
from app.services.parser import parse_expense_text
from config import DB_PATH, TIMEZONE

user_router = Router()

# 1. COMMANDS (Eski tugmalarni yashiramiz)
@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    full_name = message.from_user.full_name
    await message.answer(
        f"Salom, {full_name}! 👋\n\n"
        f"Men sizning shaxsiy moliyaviy yordamchingizman.\n"
        f"Xarajat kiritish uchun shunchaki matn yozing (Masalan: `Non 18000`, `2 ta non 36000` yoki `Taxi 30000`).",
        reply_markup=types.ReplyKeyboardRemove() # <--- Shu kod eski tugmalarni olib tashlaydi
    )

# 2. MENU COMMAND HANDLERS (Tepada turishi shart)
@user_router.message(F.text.in_({"⚙️ Sozlamalar", "/settings"}))
async def process_settings(message: types.Message):
    await message.answer("⚙️ Sozlamalar bo'limidasiz. Nima o'zgartiramiz?", reply_markup=get_settings_menu())

@user_router.message(F.text == "⬅️ Ortga")
async def process_back(message: types.Message):
    await message.answer("Asosiy menyuga qaytdik 🏠", reply_markup=types.ReplyKeyboardRemove())

@user_router.message(F.text.in_({"📊 Hisobot", "/report"}))
async def process_report(message: types.Message):
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT category, item_name, amount FROM expenses WHERE user_id = ? AND date = ?", 
                   (message.from_user.id, today))
    rows = cursor.fetchall()
    
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = ?", 
                   (message.from_user.id, today))
    total = cursor.fetchone()[0] or 0
    conn.close()
    
    if not rows:
        await message.answer("📅 Bugun hali hech qanday xarajat kiritilmadi.")
        return
        
    report_text = f"📊 **Bugungi hisobot** ({today})\n\n"
    
    grouped = {}
    for cat, item, amt in rows:
        if cat not in grouped: grouped[cat] = []
        grouped[cat].append(f"{item} — {amt:,} so'm")
    
    for cat, items in grouped.items():
        report_text += f"{cat}:\n"
        report_text += "\n".join([f" • {i}" for i in items]) + "\n\n"
        
    report_text += f"━━━━━━━━━━\n💰 **Jami: {total:,} so'm**"
    
    await message.answer(report_text, parse_mode="Markdown")

# 3. OXIRGI XARAJATNI BEKOR QILISH (TOZALASH) FUNKSIYASI
@user_router.message(F.text.in_({"🗑 Tozalash", "/undo"}))
async def process_undo_last(message: types.Message):
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT rowid, item_name, amount 
        FROM expenses 
        WHERE user_id = ? AND date = ? 
        ORDER BY rowid DESC LIMIT 1
    """, (message.from_user.id, today))
    
    last_record = cursor.fetchone()
    
    if not last_record:
        await message.answer("🤷‍♂️ Bugun uchun o'chirishga hech qanday xarajat topilmadi.")
        conn.close()
        return
        
    rowid, item_name, amount = last_record
    
    cursor.execute("DELETE FROM expenses WHERE rowid = ?", (rowid,))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"🗑 **O'chirildi!**\n\n"
        f"Bekor qilingan xarajat:\n"
        f"🔹 {item_name} — {amount:,} so'm\n\n"
        f"Ushbu summa bugungi hisobotdan muvaffaqiyatli olib tashlandi. ✅", 
        parse_mode="Markdown"
    )

# 4. GENERAL INPUT HANDLER (Eng pastda turishi shart)
@user_router.message(F.text)
async def process_expense_input(message: types.Message):
    # Buyruqlarni xarajat deb o'ylab xato qilmasligi uchun himoya
    if message.text.startswith('/'):
        await message.answer("⚠️ Kechirasiz, bunday buyruq hozircha ishlamaydi.")
        return

    text = message.text.strip()
    parsed_items = parse_expense_text(text)
    
    if not parsed_items:
        await message.answer("⚠️ Iltimos, xarajatni to'g'ri kiriting.\nMasalan:\n`Non 18000`\n`Gril 4 ta 62000`")
        return
        
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_sum = 0
    response_text = f"✅ **Xarajatlar saqlandi!**\n📅 Vaqt: {current_date} {current_time}\n\n"
    
    for item in parsed_items:
        item_name = item['item_name']
        amount = item['amount']
        category = item['category']
        
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, item_name, category, date, time) VALUES (?, ?, ?, ?, ?, ?)",
            (message.from_user.id, amount, item_name, category, current_date, current_time)
        )
        
        total_sum += amount
        response_text += f"🔹 {item_name} — {amount:,} so'm ({category})\n"
        
    conn.commit()
    conn.close()
    
    if len(parsed_items) > 1:
        response_text += f"\n━━━━━━━━━━\n💰 **Chek bo'yicha jami: {total_sum:,} so'm**"
        
    await message.answer(response_text, parse_mode="Markdown")
