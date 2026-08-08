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
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# DB faylidan funksiyalarni import qilish
from app.database.db import (
    init_db,
    add_user,
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
    income_amount = State()
    expense_choice = State()  # Xarajatni qayerdan ayirishni tanlash uchun yangi holat

# --- BOT BUYRUQLAR MENYUSINI SOZLASH ---
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish 🚀"),
        BotCommand(command="kirim", description="Balansga pul qo'shish 💰"),
        BotCommand(command="kirim_ochirish", description="Oxirgi kirimni o'chirish ❌"),
        BotCommand(command="balans", description="Joriy balanslarni tekshirish 💳"),
        BotCommand(command="balans_tozalash", description="Balansni noldan boshlash 🗑"),
        BotCommand(command="tozalash", description="Oxirgi xarajatni o'chirish 🗑"),
        BotCommand(command="kunlik", description="Kunlik hisobot 📊"),
        BotCommand(command="haftalik", description="Haftalik hisobot 📅"),
        BotCommand(command="oylik", description="Oylik hisobot 📈")
    ]
    await bot.set_my_commands(commands)

# --- STANDARD KATEGORIYALARni BAZAGA QO'SHISH ---
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
    elif any(w in name_lower for w in ["non", "shakar", "un", "kartoshka", "sariyog", "yog'", "yog", "sut", "choy", "go'sht", "gosht", "tuxum", "guruch", "makaron", "kolbasa", "sir", "tuz", "meva", "sabzi", "piyoz", "garox"]):
        return "Magazin"
    else:
        return "Boshqa"

# ================= 1. KIRIM VA BALANS QISMI =================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT card_balance, cash_balance, balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    card_bal, cash_bal, total_bal = row if row else (0, 0, 0)

    await message.answer(
        f"Assalomu alaykum! Xarajatlarni hisoblab boruvchi botga xush kelibsiz. 🚀\n\n"
        f"💳 <b>Plastik karta:</b> {card_bal:,.0f} so'm\n"
        f"💵 <b>Naqd pul:</b> {cash_bal:,.0f} so'm\n"
        f"💰 <b>Jami balans:</b> {total_bal:,.0f} so'm\n\n"
        f"📥 <b>Kirim qilish uchun:</b> <code>/kirim</code> buyrug'ini bosing\n"
        f"❌ <b>Oxirgi kirimni o'chirish:</b> <code>/kirim_ochirish</code>\n"
        f"🗑 <b>Balansni tozalash:</b> <code>/balans_tozalash</code>\n\n"
        f"🛒 <b>Xarajat qilish:</b>\n"
        f"1️⃣ <code>non 2 ta 3500</code>\n"
        f"2️⃣ <code>sariyog 15000</code>",
        parse_mode="HTML"
    )

@router.message(Command("balans"))
async def cmd_balans(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT card_balance, cash_balance, balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    card_bal, cash_bal, total_bal = row if row else (0, 0, 0)
    
    await message.answer(
        f"💳 <b>Balans hisoboti:</b>\n\n"
        f"💳 Plastik karta: {card_bal:,.0f} so'm\n"
        f"💵 Naqd pul: {cash_bal:,.0f} so'm\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami balans: {total_bal:,.0f} so'm</b>",
        parse_mode="HTML"
    )

@router.message(Command("balans_tozalash"))
async def cmd_balans_tozalash(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET card_balance = 0, cash_balance = 0, balance = 0, last_income = 0, last_income_type = 'cash' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await message.answer("🗑 <b>Barcha balansingiz (Plastik va Naqd) 0 so'm qilib tozalandi!</b>", parse_mode="HTML")

@router.message(Command("kirim"))
async def cmd_kirim(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Plastik karta", callback_data="inc_card"),
            InlineKeyboardButton(text="💵 Naqd pul", callback_data="inc_cash")
        ]
    ])
    await message.answer("📥 Qaysi balansga pul qo'shmoqchisiz? Tanlang:", reply_markup=keyboard)

@router.callback_query(F.data.in_({"inc_card", "inc_cash"}))
async def process_income_choice(callback: types.CallbackQuery, state: FSMContext):
    inc_type = "card" if callback.data == "inc_card" else "cash"
    type_name = "Plastik karta" if inc_type == "card" else "Naqd pul"
    
    await state.update_data(income_type=inc_type)
    await state.set_state(FSM.income_amount)
    
    await callback.message.edit_text(f"💰 <b>{type_name}</b> uchun summani kiriting (masalan: 1000000):", parse_mode="HTML")
    await callback.answer()

@router.message(StateFilter(FSM.income_amount), F.text)
async def process_income_amount(message: types.Message, state: FSMContext):
    text = re.sub(r'\s+', '', message.text)

    if text.isdigit():
        amount = float(text)
        user_id = message.from_user.id
        data = await state.get_data()
        inc_type = data.get("income_type", "cash")
        
        add_user(user_id)
        conn = get_connection()
        cursor = conn.cursor()
        
        if inc_type == "card":
            cursor.execute("UPDATE users SET card_balance = card_balance + ?, last_income = ?, last_income_type = ? WHERE user_id = ?", (amount, amount, 'card', user_id))
        else:
            cursor.execute("UPDATE users SET cash_balance = cash_balance + ?, last_income = ?, last_income_type = ? WHERE user_id = ?", (amount, amount, 'cash', user_id))
            
        cursor.execute("UPDATE users SET balance = card_balance + cash_balance WHERE user_id = ?", (user_id,))
        conn.commit()
        
        cursor.execute("SELECT card_balance, cash_balance, balance FROM users WHERE user_id = ?", (user_id,))
        card_bal, cash_bal, total_bal = cursor.fetchone()
        conn.close()

        type_label = "Plastik karta" if inc_type == "card" else "Naqd pul"
        await message.answer(
            f"✅ <b>{type_label}</b>ga {amount:,.0f} so'm qo'shildi.\n\n"
            f"💳 Plastik: {card_bal:,.0f} so'm\n"
            f"💵 Naqd: {cash_bal:,.0f} so'm\n"
            f"💰 Jami balans: {total_bal:,.0f} so'm",
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
    cursor.execute("SELECT card_balance, cash_balance, last_income, last_income_type FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row or row[2] <= 0:
        await message.answer("⚠️ O'chirish uchun oxirgi kirim topilmadi yoki allaqachon bekor qilingan.")
        conn.close()
        return
        
    card_bal, cash_bal, last_income, last_income_type = row
    
    if last_income_type == 'card':
        card_bal -= last_income
    else:
        cash_bal -= last_income
        
    cursor.execute(
        "UPDATE users SET card_balance = ?, cash_balance = ?, balance = ?, last_income = 0, last_income_type = 'cash' WHERE user_id = ?", 
        (card_bal, cash_bal, card_bal + cash_bal, user_id)
    )
    conn.commit()
    conn.close()
    
    type_label = "Plastik karta" if last_income_type == 'card' else "Naqd pul"
    await message.answer(
        f"❌ <b>Oxirgi kirim bekor qilindi ({type_label}):</b>\n"
        f"🔸 {last_income:,.0f} so'm ayrildi.\n\n"
        f"💳 Plastik: {card_bal:,.0f} so'm\n"
        f"💵 Naqd: {cash_bal:,.0f} so'm\n"
        f"💰 Jami balans: {card_bal + cash_bal:,.0f} so'm",
        parse_mode="HTML"
    )

# ================= 2. MENYU BUYRUQLARI (TOZALASH VA HISOBOTLAR) =================

@router.message(Command("tozalash"))
async def cmd_tozalash(message: types.Message):
    user_id = message.from_user.id
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, amount, item_name, payment_type FROM expenses 
            WHERE user_id = ? ORDER BY id DESC LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
    except Exception:
        cursor.execute('''
            SELECT id, amount, item_name FROM expenses 
            WHERE user_id = ? ORDER BY id DESC LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        if row:
            row = (*row, 'cash')
            
    if row:
        exp_id, amount, item_name, pay_type = row
        cursor.execute('DELETE FROM expenses WHERE id = ?', (exp_id,))
        
        # Bug fix: Ayirishni va total hisoblashni alohida ajratdik
        if pay_type == 'card':
            cursor.execute('UPDATE users SET card_balance = card_balance + ? WHERE user_id = ?', (amount, user_id))
        else:
            cursor.execute('UPDATE users SET cash_balance = cash_balance + ? WHERE user_id = ?', (amount, user_id))
            
        cursor.execute('UPDATE users SET balance = card_balance + cash_balance WHERE user_id = ?', (user_id,))
        conn.commit()
        
        cursor.execute("SELECT card_balance, cash_balance, balance FROM users WHERE user_id = ?", (user_id,))
        card_bal, cash_bal, total_bal = cursor.fetchone()
        
        pay_label = "💳 Plastik" if pay_type == 'card' else "💵 Naqd"
        await message.answer(
            f"🗑 <b>Oxirgi xarajat bekor qilindi:</b>\n"
            f"🔸 {item_name} — {int(amount):,} so'm\n"
            f"🔄 Summa <b>{pay_label}</b> hisobiga qaytarildi.\n\n"
            f"💳 Plastik: {card_bal:,.0f} so'm\n"
            f"💵 Naqd: {cash_bal:,.0f} so'm\n"
            f"💰 Jami balans: {total_bal:,.0f} so'm",
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


# ================= 3. XARAJATLARNI MATNDAN O'QISH VA TANLOV =================

@router.message(StateFilter(None), F.text)
async def process_text_message(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        return

    user_id = message.from_user.id
    add_user(user_id)
    lines = message.text.strip().split('\n')

    pattern_unit = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr|m|metr)\s+([\d\s]+)$", re.IGNORECASE)
    pattern_simple = re.compile(r"^(.*?)\s+([\d\s]+)$", re.IGNORECASE)

    parsed_expenses = []
    total_expense = 0
    
    tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories")
        cat_rows = cursor.fetchall()
        conn.close()
        cat_dict = {name.lower(): cat_id for cat_id, name in cat_rows}

        for line in lines:
            line_text = line.strip()
            if not line_text:
                continue

            match_unit = pattern_unit.match(line_text)
            match_simple = pattern_simple.match(line_text)

            if match_unit:
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

                parsed_expenses.append({
                    "category": cat_name, 
                    "cat_id": cat_id, 
                    "name": item_full_name, 
                    "amount": line_total,
                    "date_str": date_str,
                    "time_str": time_str
                })
                total_expense += line_total

            elif match_simple:
                name = match_simple.group(1).strip().capitalize()
                price_str = match_simple.group(2)
                line_total = float(re.sub(r'\s+', '', price_str))
                item_full_name = name

                cat_name = determine_category(name)
                cat_id = cat_dict.get(cat_name.lower(), 1)

                parsed_expenses.append({
                    "category": cat_name, 
                    "cat_id": cat_id, 
                    "name": item_full_name, 
                    "amount": line_total,
                    "date_str": date_str,
                    "time_str": time_str
                })
                total_expense += line_total

    except Exception as e:
        logging.error(f"Process text error: {e}", exc_info=True)
        await message.answer("❌ Xatolik yuz berdi. Iltimos, xabarni to'g'ri formatda yuboring.")
        return

    if not parsed_expenses:
        await message.answer(
            "⚠️ Xabarni to'g'ri formatda kiriting:\n\n"
            "🛒 Xarajat: <code>non 2 ta 3500</code> yoki <code>sariyog 15000</code>",
            parse_mode="HTML"
        )
        return

    # FSM State'ga xarajatlarni saqlaymiz va tanlov tugmalarini chiqaramiz
    await state.update_data(pending_expenses=parsed_expenses, total_expense=total_expense)
    await state.set_state(FSM.expense_choice)

    grouped = {}
    for exp in parsed_expenses:
        c = exp["category"]
        if c not in grouped:
            grouped[c] = []
        grouped[c].append(exp)

    preview_text = "🛒 <b>Xarajatlar ro'yxati:</b>\n"
    for cat, items in grouped.items():
        preview_text += f"📂 <b>{cat}:</b>\n"
        for item in items:
            preview_text += f"  • {item['name']} — {int(item['amount']):,} so'm\n"
        preview_text += "\n"

    preview_text += f"💰 <b>Jami xarajat: {int(total_expense):,} so'm</b>\n\n👇 <b>Ushbu xarajatni qaysi hisobdan ayiramiz?</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Plastik karta", callback_data="exp_card"),
            InlineKeyboardButton(text="💵 Naqd pul", callback_data="exp_cash")
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="exp_cancel")
        ]
    ])

    await message.answer(preview_text, parse_mode="HTML", reply_markup=keyboard)


# ================= 4. XARAJATNI TASDIQLASH (CALLBACK) =================

@router.callback_query(StateFilter(FSM.expense_choice), F.data.in_({"exp_card", "exp_cash", "exp_cancel"}))
async def process_expense_choice(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "exp_cancel":
        await callback.message.edit_text("❌ <b>Xarajat yozish bekor qilindi.</b>", parse_mode="HTML")
        await state.clear()
        return
        
    data = await state.get_data()
    pending_expenses = data.get("pending_expenses", [])
    total_expense = data.get("total_expense", 0)
    user_id = callback.from_user.id
    
    pay_type = "card" if callback.data == "exp_card" else "cash"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for exp in pending_expenses:
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category_id, item_name, date, time, payment_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, exp['amount'], exp['cat_id'], exp['name'], exp['date_str'], exp['time_str'], pay_type)
        )
        
    # Bug fix: Ayirishni va total hisoblashni alohida ajratdik
    if pay_type == "card":
        cursor.execute("UPDATE users SET card_balance = card_balance - ? WHERE user_id = ?", (total_expense, user_id))
    else:
        cursor.execute("UPDATE users SET cash_balance = cash_balance - ? WHERE user_id = ?", (total_expense, user_id))
        
    cursor.execute("UPDATE users SET balance = card_balance + cash_balance WHERE user_id = ?", (user_id,))
    conn.commit()
    
    cursor.execute("SELECT card_balance, cash_balance, balance FROM users WHERE user_id = ?", (user_id,))
    card_bal, cash_bal, total_bal = cursor.fetchone()
    conn.close()

    # Tasdiqlangan xabar matni
    grouped = {}
    for exp in pending_expenses:
        c = exp["category"]
        if c not in grouped:
            grouped[c] = []
        grouped[c].append(exp)

    response_parts = ["✅ <b>Xarajatlar muvaffaqiyatli saqlandi:</b>\n"]
    for cat, items in grouped.items():
        response_parts.append(f"📂 <b>{cat}:</b>")
        for item in items:
            response_parts.append(f"  • {item['name']} — {int(item['amount']):,} so'm")
        response_parts.append("")
        
    pay_label = "💳 Plastik karta" if pay_type == "card" else "💵 Naqd pul"
    response_parts.append(f"💰 <b>Jami: {int(total_expense):,} so'm</b> ({pay_label}dan ayrildi)")
    
    response_parts.append(
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Plastik: {card_bal:,.0f} so'm\n"
        f"💵 Naqd: {cash_bal:,.0f} so'm\n"
        f"💰 <b>Joriy balans: {total_bal:,.0f} so'm</b>"
    )
    
    await callback.message.edit_text("\n".join(response_parts), parse_mode="HTML")
    await state.clear()


# ================= ASOSIY ISHGA TUSHIRISH =================

async def main():
    init_db()
    seed_default_categories()

    conn = get_connection()
    cursor = conn.cursor()
    
    try: cursor.execute("ALTER TABLE users ADD COLUMN card_balance REAL DEFAULT 0")
    except Exception: pass
    
    try: cursor.execute("ALTER TABLE users ADD COLUMN cash_balance REAL DEFAULT 0")
    except Exception: pass
    
    try: cursor.execute("ALTER TABLE users ADD COLUMN last_income REAL DEFAULT 0")
    except Exception: pass
    
    try: cursor.execute("ALTER TABLE users ADD COLUMN last_income_type TEXT DEFAULT 'cash'")
    except Exception: pass

    try: cursor.execute("ALTER TABLE expenses ADD COLUMN payment_type TEXT DEFAULT 'cash'")
    except Exception: pass

    conn.commit()
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
