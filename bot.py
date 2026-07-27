import asyncio
import logging
import os
import re
import threading
from datetime import datetime, timedelta
import pytz
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand
from flask import Flask

# DB faylidan funksiyalarni import qilish
from app.database.db import (
    init_db,
    add_user,
    get_balance,
    get_connection
)

# Logging sozlamasi
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- 1. FLASK SERVER (Render 24/7 ishlashi uchun) ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Expense Tracker Bot is running 24/7! 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- 2. BOT SOZLAMALARI ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Render Environment'ga qo'shing.")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

class FSM(StatesGroup):
    income = State()

# --- BOT BUYRUQLAR MENYUSINI SOZLASH ---
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish 🚀"),
        BotCommand(command="kirim", description="Balansga pul qo'shish 💰"),
        BotCommand(command="kirim_ochirish", description="Oxirgi kirimni o'chirish ❌"),
        BotCommand(command="balans", description="Joriy balansni tekshirish 💳"),
        BotCommand(command="tozalash", description="Oxirgi xarajatni o'chirish 🗑"),
        BotCommand(command="kunlik", description="Kunlik hisobot 📊"),
        BotCommand(command="haftalik", description="Haftalik hisobot 📅"),
        BotCommand(command="oylik", description="Oylik hisobot 📈")
    ]
    await bot.set_my_commands(commands)

# --- STANDARD KATEGORIYALARNI BAZAGA QO'SHISH ---
def seed_default_categories():
    categories = ["Magazin", "Zapravka", "Apteka", "Stroy magazin", "Boshqa"]
    conn = get_connection()
    cursor = conn.cursor()
    for cat in categories:
        cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
    conn.commit()
    conn.close()

# --- AVTOMATIK KATEGORIYAGA AJRATISH ---
def determine_category(name: str) -> str:
    name_lower = name.lower()
    if any(w in name_lower for w in ["benzin", "metan", "propan", "zapravka", "ai-92", "ai-95", "gaz"]):
        return "Zapravka"
    elif any(w in name_lower for w in ["dori", "tabletka", "apteka", "vitamin", "salfetka", "shpris"]):
        return "Apteka"
    elif any(w in name_lower for w in ["sement", "kraska", "mix", "truba", "kafel", "shurup", "bolt", "qum"]):
        return "Stroy magazin"
    elif any(w in name_lower for w in ["non", "shakar", "un", "kartoshka", "sariyog", "yog'", "yog", "sut", "choy", "go'sht", "gosht", "tuxum", "guruch", "makaron", "kolbasa", "sir", "tuz", "meva", "sabzi", "piyoz"]):
        return "Magazin"
    else:
        return "Boshqa"

# ================= 1. KIRIM VA BALANS QISMI (2 USULDA) =================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    current_balance = get_balance(user_id)
    await message.answer(
        f"Assalomu alaykum! Xarajatlarni hisoblab boruvchi botga xush kelibsiz. 🚀\n\n"
        f"💳 Joriy balansingiz: {current_balance:,.0f} so'm\n\n"
        f"📥 **Kirim qilish 2 usulda:**\n"
        f"1️⃣ `/kirim` yoki `/kirim 15 000 000`\n"
        f"2️⃣ `+ 15 000 000` yoki `maosh 15 000 000`\n\n"
        f"❌ **Oxirgi kirimni o'chirish:** `/kirim_ochirish`\n\n"
        f"🛒 **Xarajat qilish 2 usulda:**\n"
        f"1️⃣ `non 2 ta 3500`\n"
        f"2️⃣ `sariyog 15000`",
        parse_mode="HTML"
    )

@router.message(Command("balans"))
async def cmd_balans(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    current_balance = get_balance(user_id)
    await message.answer(f"💳 <b>Joriy balansingiz:</b> {current_balance:,.0f} so'm", parse_mode="HTML")

@router.message(Command("kirim"))
async def cmd_kirim(message: types.Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    user_id = message.from_user.id
    add_user(user_id)

    if len(args) > 1:
        text_clean = re.sub(r'\s+', '', args[1])
        if text_clean.isdigit():
            amount = float(text_clean)
            
            # Bazaga yozish va oxirgi kirimni saqlash
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ?, last_income = ? WHERE user_id = ?", (amount, amount, user_id))
            conn.commit()
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            current_balance = cursor.fetchone()[0]
            conn.close()

            await message.answer(
                f"✅ Balansga {amount:,.0f} so'm qo'shildi.\n💳 Joriy balans: {current_balance:,.0f} so'm",
                parse_mode="HTML"
            )
            return

    await message.answer("💰 Balansga qo'shmoqchi bo'lgan summani kiriting (masalan: 1 000 000):")
    await state.set_state(FSM.income)

@router.message(StateFilter(FSM.income), F.text)
async def process_income(message: types.Message, state: FSMContext):
    text = re.sub(r'\s+', '', message.text)

    if text.isdigit():
        amount = float(text)
        user_id = message.from_user.id
        
        add_user(user_id)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ?, last_income = ? WHERE user_id = ?", (amount, amount, user_id))
        conn.commit()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        current_balance = cursor.fetchone()[0]
        conn.close()

        await message.answer(
            f"✅ Balansga {amount:,.0f} so'm qo'shildi.\n💳 Joriy balans: {current_balance:,.0f} so'm",
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await message.answer("❌ Noto'g'ri summa kiritildi. Iltimos, faqat raqam kiriting:")

@router.message(Command("kirim_ochirish"))
async def cmd_kirim_ochirish(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, last_income FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row or row[1] <= 0:
        await message.answer("⚠️ O'chirish uchun oxirgi kirim topilmadi yoki allaqachon bekor qilingan.")
        conn.close()
        return
        
    balance, last_income = row
    new_balance = balance - last_income
    
    cursor.execute("UPDATE users SET balance = ?, last_income = 0 WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"❌ <b>Oxirgi kirim bekor qilindi:</b>\n"
        f"🔸 {last_income:,.0f} so'm ayrildi.\n\n"
        f"💳 Joriy balans: {new_balance:,.0f} so'm",
        parse_mode="HTML"
    )


# ================= 2. MENYU BUYRUQLARI (TOZALASH VA HISOBOTLAR) =================

@router.message(Command("tozalash"))
async def cmd_tozalash(message: types.Message):
    user_id = message.from_user.id
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, amount, item_name FROM expenses 
        WHERE user_id = ? ORDER BY id DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    
    if row:
        exp_id, amount, item_name = row
        cursor.execute('DELETE FROM expenses WHERE id = ?', (exp_id,))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        
        current_balance = get_balance(user_id)
        await message.answer(
            f"🗑 <b>Oxirgi xarajat bekor qilindi:</b>\n"
            f"🔸 {item_name} — {int(amount):,} so'm\n\n"
            f"💳 Joriy balans: {current_balance:,.0f} so'm",
            parse_mode="HTML"
        )
    else:
        await message.answer("⚠️ Bekor qilish uchun xarajatlar tarixi topilmadi.")
    
    conn.close()

@router.message(Command("kunlik"))
async def cmd_kunlik(message: types.Message):
    user_id = message.from_user.id
    tz = pytz.timezone("Asia/Tashkent")
    today = datetime.now(tz).strftime("%Y-%m-%d")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.name, e.item_name, e.amount, e.time 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.date = ?
    ''', (user_id, today))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"📅 <b>{today}</b>\n\nBugun uchun xarajatlar yo'q. 🤷‍♂️", parse_mode="HTML")
        return
        
    total = sum(row[2] for row in rows)
    grouped = {}
    for cat_name, item_name, amount, time in rows:
        if cat_name not in grouped:
            grouped[cat_name] = []
        grouped[cat_name].append((item_name, amount, time))
    
    report_lines = [f"📊 <b>Bugungi xarajatlar ({today}):</b>\n"]
    for cat, items in grouped.items():
        report_lines.append(f"📂 <b>{cat}:</b>")
        for item_name, amount, time in items:
            report_lines.append(f"  • {item_name} — {int(amount):,} so'm ({time})")
        report_lines.append("")
        
    report_lines.append(f"💰 <b>Jami kunlik xarajat: {int(total):,} so'm</b>")
    await message.answer("\n".join(report_lines), parse_mode="HTML")

@router.message(Command("haftalik"))
async def cmd_haftalik(message: types.Message):
    user_id = message.from_user.id
    tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    start_of_week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.name, e.item_name, e.amount, e.date 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.date BETWEEN ? AND ?
        ORDER BY e.date DESC
    ''', (user_id, start_of_week, today_str))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"📅 <b>Haftalik hisobot ({start_of_week} — {today_str})</b>\n\nXarajatlar mavjud emas. 🤷‍♂️", parse_mode="HTML")
        return
        
    total = sum(row[2] for row in rows)
    grouped = {}
    for cat_name, item_name, amount, date in rows:
        if cat_name not in grouped:
            grouped[cat_name] = []
        grouped[cat_name].append((item_name, amount, date))
    
    report_lines = [f"📅 <b>Haftalik xarajatlar ({start_of_week} — {today_str}):</b>\n"]
    for cat, items in grouped.items():
        report_lines.append(f"📂 <b>{cat}:</b>")
        for item_name, amount, date in items:
            report_lines.append(f"  • {item_name} — {int(amount):,} so'm ({date})")
        report_lines.append("")
        
    report_lines.append(f"💰 <b>Jami haftalik xarajat: {int(total):,} so'm</b>")
    await message.answer("\n".join(report_lines), parse_mode="HTML")

@router.message(Command("oylik"))
async def cmd_oylik(message: types.Message):
    user_id = message.from_user.id
    tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(tz)
    current_year_month = now.strftime("%Y-%m")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.name, e.item_name, e.amount, e.date 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.date LIKE ?
        ORDER BY e.date DESC
    ''', (user_id, f"{current_year_month}%"))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"📈 <b>Oylik hisobot ({current_year_month})</b>\n\nXarajatlar mavjud emas. 🤷‍♂️", parse_mode="HTML")
        return
        
    total = sum(row[2] for row in rows)
    grouped = {}
    for cat_name, item_name, amount, date in rows:
        if cat_name not in grouped:
            grouped[cat_name] = []
        grouped[cat_name].append((item_name, amount, date))
    
    report_lines = [f"📈 <b>Oylik xarajatlar ({current_year_month}):</b>\n"]
    for cat, items in grouped.items():
        report_lines.append(f"📂 <b>{cat}:</b>")
        for item_name, amount, date in items:
            report_lines.append(f"  • {item_name} — {int(amount):,} so'm ({date})")
        report_lines.append("")
        
    report_lines.append(f"💰 <b>Jami oylik xarajat: {int(total):,} so'm</b>")
    await message.answer("\n".join(report_lines), parse_mode="HTML")


# ================= 3. KIRIM VA XARAJATLARNI MATNDAN O'QISH (2 USULDA) =================

@router.message(StateFilter(None), F.text)
async def process_text_message(message: types.Message):
    if message.text.startswith('/'):
        return

    user_id = message.from_user.id
    add_user(user_id)
    lines = message.text.strip().split('\n')

    pattern_income = re.compile(r"^(\+|kirim|maosh)\s+([\d\s]+)$", re.IGNORECASE)
    pattern_unit = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr|m|metr)\s+([\d\s]+)$", re.IGNORECASE)
    pattern_simple = re.compile(r"^(.*?)\s+([\d\s]+)$", re.IGNORECASE)

    parsed_expenses = []
    total_expense = 0
    total_income_added = 0
    
    tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    cat_rows = cursor.fetchall()
    cat_dict = {name.lower(): cat_id for cat_id, name in cat_rows}

    for line in lines:
        line_text = line.strip()
        if not line_text:
            continue

        match_income = pattern_income.match(line_text)
        match_unit = pattern_unit.match(line_text)
        match_simple = pattern_simple.match(line_text)

        if match_income:
            price_str = match_income.group(2)
            inc_amount = float(re.sub(r'\s+', '', price_str))
            cursor.execute("UPDATE users SET balance = balance + ?, last_income = ? WHERE user_id = ?", (inc_amount, inc_amount, user_id))
            total_income_added += inc_amount
        elif match_unit:
            name = match_unit.group(1).strip().capitalize()
            qty_str = match_unit.group(2)
            qty = float(qty_str) if '.' in qty_str else int(qty_str)
            unit = match_unit.group(3).strip().lower()
            price_str = match_unit.group(4)
            price = float(re.sub(r'\s+', '', price_str))
            
            line_total = qty * price
            item_full_name = f"{name} {qty} {unit}"

            cat_name = determine_category(name)
            cat_id = cat_dict.get(cat_name.lower(), 1)

            add_expense(user_id=user_id, amount=line_total, category_id=cat_id, item_name=item_full_name, date=date_str, time=time_str)
            total_expense += line_total
            parsed_expenses.append({"category": cat_name, "name": item_full_name, "amount": line_total})

        elif match_simple:
            name = match_simple.group(1).strip().capitalize()
            price_str = match_simple.group(2)
            line_total = float(re.sub(r'\s+', '', price_str))
            item_full_name = name

            cat_name = determine_category(name)
            cat_id = cat_dict.get(cat_name.lower(), 1)

            add_expense(user_id=user_id, amount=line_total, category_id=cat_id, item_name=item_full_name, date=date_str, time=time_str)
            total_expense += line_total
            parsed_expenses.append({"category": cat_name, "name": item_full_name, "amount": line_total})

    conn.commit()
    conn.close()

    current_balance = get_balance(user_id)
    response_parts = []

    if total_income_added > 0:
        response_parts.append(f"✅ Balansga <b>{total_income_added:,.0f} so'm</b> kirim qo'shildi.")

    if parsed_expenses:
        grouped = {}
        for exp in parsed_expenses:
            c = exp["category"]
            if c not in grouped:
                grouped[c] = []
            grouped[c].append(exp)

        response_parts.append("🛒 <b>Xarajatlar ro'yxati:</b>")
        for cat, items in grouped.items():
            response_parts.append(f"📂 <b>{cat}:</b>")
            for item in items:
                response_parts.append(f"  • {item['name']} — {int(item['amount']):,} so'm")
            response_parts.append("")

        response_parts.append(f"💰 <b>Jami xarajat: {int(total_expense):,} so'm</b>")

    if response_parts:
        response_parts.append(f"💳 <b>Joriy balans: {current_balance:,.0f} so'm</b>")
        await message.answer("\n".join(response_parts), parse_mode="HTML")
    else:
        await message.answer(
            "⚠️ Xabarni to'g'ri formatda kiriting:\n\n"
            "📥 Kirim: `+ 15 000 000` yoki `/kirim 15 000 000`\n"
            "🛒 Xarajat: `non 2 ta 3500` yoki `sariyog 15000`",
            parse_mode="HTML"
        )


# ================= ASOSIY ISHGA TUSHIRISH =================

async def main():
    init_db()
    seed_default_categories()

    # Bazaga last_income ustunini xavfsiz qo'shish (migration)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_income REAL DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    conn.close()

    threading.Thread(target=run_flask, daemon=True).start()

    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await set_bot_commands(bot)
    
    logging.info("Telegram bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
