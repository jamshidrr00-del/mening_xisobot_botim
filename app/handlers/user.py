import logging
import sqlite3
from datetime import datetime
import pytz
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from app.keyboards.reply import get_settings_menu
from app.services.parser import parse_expense_text
from config import TIMEZONE
from app.database.db import (
    DB_PATH, add_user, update_balance, get_balance
)

user_router = Router()

# Yordamchi funksiya: kategoriya nomidan uning ID sini olish yoki bazaga qo'shib ID qaytarish
def get_or_create_category_id(cursor, category_name):
    cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
    return cursor.lastrowid

# 1. COMMANDS (Start)
@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    add_user(user_id)
    current_balance = get_balance(user_id)

    await message.answer(
        f"Salom, {full_name}! 👋\n\n"
        f"Men sizning shaxsiy moliyaviy yordamchingizman.\n"
        f"Xarajat kiritish uchun shunchaki matn yozing (Masalan: `Non 18000`, `2 ta non 36000` yoki `Taxi 30000`).\n\n"
        f"💳 Joriy balans: *{current_balance:,.0f} so'm*\n"
        f"Balansni to'ldirish uchun: `/kirim 150000`",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

# 1.1. KIRIM COMMAND (Balansni to'ldirish)
@user_router.message(Command("kirim"))
async def cmd_kirim(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Iltimos, summani to'g'ri kiriting!\nMasalan: `/kirim 150000`", parse_mode="Markdown")
        return
    
    amount = float(parts[1])
    update_balance(user_id, amount)
    current_balance = get_balance(user_id)
    
    await message.answer(
        f"✅ Hisobingizga **{amount:,.0f} so'm** qo'shildi!\n"
        f"💳 Joriy balans: **{current_balance:,.0f} so'm**",
        parse_mode="Markdown"
    )

# 2. MENU COMMAND HANDLERS
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
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.name, e.item_name, e.amount 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.date = ?
    """, (user_id, today))
    rows = cursor.fetchall()
    
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = ?", (user_id, today))
    total_res = cursor.fetchone()[0]
    total = total_res if total_res else 0.0
    
    current_balance = get_balance(user_id)
    conn.close()
    
    if not rows:
        await message.answer(f"📅 Bugun hali hech qanday xarajat kiritilmadi.\n💳 Joriy balans: **{current_balance:,.0f} so'm**", parse_mode="Markdown")
        return
        
    report_text = f"📊 **Bugungi hisobot** ({today})\n\n"
    
    grouped = {}
    for cat, item, amt in rows:
        if cat not in grouped: grouped[cat] = []
        grouped[cat].append(f"{item} — {amt:,.0f} so'm")
    
    for cat, items in grouped.items():
        report_text += f"{cat}:\n"
        report_text += "\n".join([f" • {i}" for i in items]) + "\n\n"
        
    report_text += f"━━━━━━━━━━\n💰 **Jami xarajat: {total:,.0f} so'm**\n💳 **Qolgan balans: {current_balance:,.0f} so'm**"
    
    await message.answer(report_text, parse_mode="Markdown")

# 3. OXIRGI XARAJATNI BEKOR QILISH (TOZALASH)
@user_router.message(F.text.in_({"🗑 Tozalash", "/undo"}))
async def process_undo_last(message: types.Message):
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT e.id, e.item_name, e.amount 
        FROM expenses e
        WHERE e.user_id = ? AND e.date = ? 
        ORDER BY e.id DESC LIMIT 1
    """, (user_id, today))
    
    last_record = cursor.fetchone()
    
    if not last_record:
        await message.answer("🤷‍♂️ Bugun uchun o'chirishga hech qanday xarajat topilmadi.")
        conn.close()
        return
        
    expense_id, item_name, amount = last_record
    
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    
    update_balance(user_id, amount)
    current_balance = get_balance(user_id)
    
    await message.answer(
        f"🗑 **O'chirildi!**\n\n"
        f"Bekor qilingan xarajat:\n"
        f"🔹 {item_name} — {amount:,.0f} so'm\n\n"
        f"Ushbu summa balansingizga qaytarildi. ✅\n"
        f"💳 Qolgan balans: **{current_balance:,.0f} so'm**", 
        parse_mode="Markdown"
    )

# 4. GENERAL INPUT HANDLER
@user_router.message(F.text)
async def process_expense_input(message: types.Message):
    if message.text.startswith('/'):
        await message.answer("⚠️ Kechirasiz, bunday buyruq hozircha ishlamaydi.")
        return

    text = message.text.strip()
    parsed_items = parse_expense_text(text)
    
    if not parsed_items:
        await message.answer("⚠️ Iltimos, xarajatni to'g'ri kiriting.\nMasalan:\n`Non 18000`\n`Gril 4 ta 62000`", parse_mode="Markdown")
        return
        
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    user_id = message.from_user.id
    
    add_user(user_id)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_sum = 0
    response_text = f"✅ **Xarajatlar saqlandi!**\n📅 Vaqt: {current_date} {current_time}\n\n"
    
    for item in parsed_items:
        item_name = item['item_name']
        amount = item['amount']
        category_name = item['category']
        
        category_id = get_or_create_category_id(cursor, category_name)
        
        cursor.execute('''
            INSERT INTO expenses (user_id, amount, category_id, item_name, date, time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, amount, category_id, item_name, current_date, current_time))
        
        total_sum += amount
        response_text += f"🔹 {item_name} — {amount:,.0f} so'm ({category_name})\n"
        
    cursor.execute('''
        UPDATE users SET balance = balance - ? WHERE user_id = ?
    ''', (total_sum, user_id))
    
    conn.commit()
    conn.close()
    
    current_balance = get_balance(user_id)
    
    response_text += f"\n━━━━━━━━━━\n💰 **Jami xarajat: {total_sum:,.0f} so'm**\n💳 **Qolgan balans: {current_balance:,.0f} so'm**"
        
    await message.answer(response_text, parse_mode="Markdown")
