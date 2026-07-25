import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
import pytz
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aiogram import Router, F, Bot, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# O'zingizning fayl tuzilmangizga mos ravishda chaqirasiz
from app.database.db import DB_PATH, add_user, update_balance, get_balance, get_user_lang, set_user_lang
from app.services.parser import parse_expense_text
from app.keyboards.reply import get_main_menu, get_settings_menu
from config import TIMEZONE

user_router = Router()

class FSM(StatesGroup):
    income = State()
    exp_amount = State()
    exp_name = State()
    exp_category = State()
    new_category = State()
    search_date = State()

# ================= KUNLIK AVTOMAT HISOBOT =================
async def send_daily_reports(bot: Bot):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    report_date = now.strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance FROM users")
    users = cursor.fetchall()
    
    for user_id, balance in users:
        cursor.execute("""
            SELECT c.name, SUM(e.amount) 
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = ? AND e.date = ?
            GROUP BY c.name
        """, (user_id, report_date))
        rows = cursor.fetchall()
        
        if rows:
            text = f"🌖 **Kun yopildi! Bugungi ({report_date}) hisobot:**\n\n"
            total = 0
            for cat_name, amt in rows:
                text += f"🔹 {cat_name}: {amt:,.0f} so'm\n"
                total += amt
            text += f"\n━━━━━━━━━━\n💰 **Jami xarajat: {total:,.0f} so'm**\n💳 **Joriy balans: {balance:,.0f} so'm**"
            
            try:
                await bot.send_message(user_id, text, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Avtomatik xabar yuborishda xatolik ({user_id}): {e}")
    conn.close()

async def schedule_daily_report(bot: Bot):
    tz = pytz.timezone(TIMEZONE)
    while True:
        now = datetime.now(tz)
        target = now.replace(hour=23, minute=59, second=50, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
            
        sleep_time = (target - now).total_seconds()
        await asyncio.sleep(sleep_time)
        await send_daily_reports(bot)

@user_router.startup()
async def on_startup(bot: Bot):
    asyncio.create_task(schedule_daily_report(bot))

# ================= KEYBOARDLAR =================
def get_categories_kb():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    rows = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for cat_id, name in rows:
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"cat_{cat_id}")])
    keyboard.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_categories_manage_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="add_cat")],
        [InlineKeyboardButton(text="🗑 Kategoriya o'chirish", callback_data="del_cat_menu")]
    ])

def get_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")]
    ])

@user_router.callback_query(F.data == "cancel_action")
async def cancel_action_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Amal bekor qilindi.")
    await callback.answer()

# ================= ASOSIY MENYU =================
@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    add_user(user_id)
    balance = get_balance(user_id)
    
    await message.answer(
        f"Salom, {message.from_user.full_name}! 👋\n\n🤖 Shaxsiy moliyaviy yordamchingizga xush kelibsiz.\n💳 Joriy balans: **{balance:,.0f} so'm**",
        reply_markup=get_main_menu(message),
        parse_mode="Markdown"
    )

@user_router.message(F.text.in_({"⚙️ Sozlamalar", "⚙️ Настройки", "⚙️ Settings", "/settings"}))
async def process_settings(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Sozlamalar bo'limi. Kerakli amalni tanlang:", reply_markup=get_settings_menu(message))

@user_router.message(F.text.in_({"🇺🇿 O'zbekcha", "🇷🇺 Русский", "🇬🇧 English"}))
async def change_language(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if "O'zbekcha" in message.text:
        set_user_lang(user_id, 'uz')
    elif "Русский" in message.text:
        set_user_lang(user_id, 'ru')
    elif "English" in message.text:
        set_user_lang(user_id, 'en')
    await message.answer("✅ Til muvaffaqiyatli o'zgartirildi!", reply_markup=get_main_menu(message))

@user_router.message(F.text.in_({"⬅️ Ortga", "⬅️ Назад", "⬅️ Back"}))
async def process_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu", reply_markup=get_main_menu(message))

# ================= DAROMAD KIRITISH =================
@user_router.message(F.text.in_({"➕ Daromad kiritish", "➕ Добавить доход", "➕ Add Income"}))
async def process_income_btn(message: types.Message, state: FSMContext):
    await state.set_state(FSM.income)
    await message.answer(
        "💰 Daromad summasini kiriting (masalan: `1500000` yoki `15 000 000`):", 
        reply_markup=get_cancel_kb(), 
        parse_mode="Markdown"
    )

@user_router.message(F.state == FSM.income, F.text)
async def process_income_amount(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
        
    text = message.text.strip().replace(" ", "").replace(",", ".")
    if not text.replace('.', '', 1).isdigit():
        await message.answer(
            "❌ Noto'g'ri qiymat. Iltimos, faqat raqam kiriting:\n(Jarayonni to'xtatish uchun 'Bekor qilish'ni bosing)", 
            reply_markup=get_cancel_kb()
        )
        return
        
    amount = float(text)
    if amount <= 0:
        await message.answer("❌ Summa 0 dan katta bo'lishi kerak. Qaytadan kiriting:", reply_markup=get_cancel_kb())
        return
        
    user_id = message.from_user.id
    update_balance(user_id, amount)
    balance = get_balance(user_id)
    await state.clear()
    
    undo_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Oxirgi kirimni o'chirish", callback_data=f"undo_inc_{amount}")]
    ])
    await message.answer(
        f"✅ Hisobingizga **{amount:,.0f} so'm** qo'shildi!\n💳 Joriy balans: **{balance:,.0f} so'm**",
        reply_markup=undo_kb, 
        parse_mode="Markdown"
    )

@user_router.callback_query(F.data.startswith("undo_inc_"))
async def undo_income_callback(callback: types.CallbackQuery):
    amount = float(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Balansdan kiritilgan pulni olib tashlash
    update_balance(user_id, -amount)
    new_balance = get_balance(user_id)
    
    await callback.message.edit_text(
        f"🗑 Kiritilgan **{amount:,.0f} so'm** daromad bekor qilindi va balansdan ayirildi!\n💳 Joriy balans: **{new_balance:,.0f} so'm**", 
        parse_mode="Markdown"
    )
    await callback.answer("O'chirildi!")

# ================= XARAJAT KIRITISH =================
@user_router.message(F.text.in_({"➕ Xarajat kiritish", "➕ Добавить расход", "➕ Add Expense"}))
async def process_expense_btn(message: types.Message, state: FSMContext):
    await state.set_state(FSM.exp_amount)
    await message.answer(
        "💳 Xarajat summasini kiriting (masalan: `50000` yoki `50 000`):", 
        reply_markup=get_cancel_kb(), 
        parse_mode="Markdown"
    )

@user_router.message(F.state == FSM.exp_amount, F.text)
async def process_exp_amount(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
        
    text = message.text.strip().replace(" ", "").replace(",", ".")
    if not text.replace('.', '', 1).isdigit():
        await message.answer(
            "❌ Xato summa. Faqat raqam kiriting (masalan: `50000` yoki `50 000`):", 
            reply_markup=get_cancel_kb(), 
            parse_mode="Markdown"
        )
        return
        
    amount = float(text)
    if amount <= 0:
        await message.answer("❌ Summa 0 dan katta bo'lishi kerak:", reply_markup=get_cancel_kb())
        return
        
    await state.update_data(amount=amount)
    await state.set_state(FSM.exp_name)
    await message.answer("📝 Xarajat nomini kiriting (masalan: Non):", reply_markup=get_cancel_kb(), parse_mode="Markdown")

@user_router.message(F.state == FSM.exp_name, F.text)
async def process_exp_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(item_name=message.text.strip())
    await state.set_state(FSM.exp_category)
    await message.answer("📂 Kategoriyani tanlang:", reply_markup=get_categories_kb())

@user_router.callback_query(F.state == FSM.exp_category, F.data.startswith("cat_"))
async def process_exp_category_select(callback: types.CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    amount = data['amount']
    item_name = data['item_name']
    
    user_id = callback.from_user.id
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expenses (user_id, amount, category_id, item_name, date, time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, category_id, item_name, now.strftime("%Y-%m-%d"), now.strftime("%H:%M")))
    exp_id = cursor.lastrowid
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    
    balance = get_balance(user_id)
    await state.clear()
    
    undo_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Oxirgi xarajatni o'chirish", callback_data=f"undo_exp_{exp_id}_{amount}")]
    ])
    await callback.message.edit_text(
        f"✅ Saqlandi!\n🔹 {item_name} — {amount:,.0f} so'm\n💳 Balans: **{balance:,.0f} so'm**", 
        reply_markup=undo_kb, 
        parse_mode="Markdown"
    )

@user_router.callback_query(F.data.startswith("undo_exp_"))
async def undo_expense_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    exp_id = int(parts[2])
    amount = float(parts[3])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    
    new_balance = get_balance(user_id)
    await callback.message.edit_text(
        f"🗑 Oxirgi xarajat bekor qilindi va pul balansga qaytarildi!\n💳 Joriy balans: **{new_balance:,.0f} so'm**", 
        parse_mode="Markdown"
    )
    await callback.answer("Muvaffaqiyatli o'chirildi!")

# ================= KATEGORIYALARNI BOSHQARISH =================
@user_router.message(F.text.in_({"📂 Kategoriyalar", "📂 Категории", "📂 Categories"}))
async def process_categories_menu(message: types.Message, state: FSMContext):
    await message.answer("📂 Kategoriyani boshqarish:", reply_markup=get_categories_manage_kb())

@user_router.callback_query(F.data == "add_cat")
async def callback_add_cat(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSM.new_category)
    await callback.message.answer("📂 Yangi kategoriya nomini kiriting:", reply_markup=get_cancel_kb())
    await callback.answer()

@user_router.message(F.state == FSM.new_category, F.text)
async def save_new_category(message: types.Message, state: FSMContext):
    cat_name = message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
        conn.commit()
        await message.answer(f"✅ '{cat_name}' kategoriyasi muvaffaqiyatli qo'shildi!", reply_markup=get_main_menu(message))
    except sqlite3.IntegrityError:
        await message.answer("⚠️ Bu kategoriya allaqachon mavjud!")
    conn.close()
    await state.clear()

@user_router.callback_query(F.data == "del_cat_menu")
async def callback_del_cat_menu(callback: types.CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    rows = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for cat_id, name in rows:
        keyboard.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"delcat_{cat_id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cancel_action")])
    await callback.message.edit_text("O'chiriladigan kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@user_router.callback_query(F.data.startswith("delcat_"))
async def callback_delete_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
    row = cursor.fetchone()
    if row:
        cat_name = row[0]
        cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        await callback.message.edit_text(f"🗑 '{cat_name}' kategoriyasi o'chirildi!")
    conn.close()
    await callback.answer()

# ================= QIDIRUV VA DIAGRAMMALAR =================
@user_router.message(F.text.in_({"📊 Diagramma", "📊 Диаграмма", "📊 Chart"}))
async def process_chart(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name, SUM(e.amount) 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ?
        GROUP BY c.name
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("🤷‍♂️ Diagramma tuzish uchun xarajatlar mavjud emas.")
        return
        
    categories = [row[0] for row in rows]
    amounts = [row[1] for row in rows]
    
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    ax.axis('equal')
    ax.set_title("Xarajatlar taqsimoti")
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    plt.close(fig)
    
    photo = BufferedInputFile(buffer.getvalue(), filename="chart.png")
    await message.answer_photo(photo, caption="📊 Sizning umumiy xarajatlar diagrammangiz:")

@user_router.message(F.text.in_({"🔍 Qidiruv", "🔍 Поиск", "🔍 Search"}))
async def process_search_menu(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Kategoriya bo'yicha", callback_data="search_cat_menu")],
        [InlineKeyboardButton(text="📅 Sana bo'yicha", callback_data="search_date_prompt")]
    ])
    await message.answer("🔍 Qidiruv turini tanlang:", reply_markup=kb)

@user_router.callback_query(F.data == "search_cat_menu")
async def callback_search_cat_menu(callback: types.CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    rows = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for cat_id, name in rows:
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"schcat_{cat_id}")])
    await callback.message.edit_text("🔍 Qidirish uchun kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@user_router.callback_query(F.data.startswith("schcat_"))
async def callback_search_by_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.item_name, e.amount, e.date, c.name 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.category_id = ?
        ORDER BY e.date DESC
    """, (user_id, cat_id))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.edit_text("🤷‍♂️ Bu kategoriyada xarajatlar topilmadi.")
        return
        
    text = f"📂 **Kategoriya bo'yicha qidiruv natijasi:**\n\n"
    total = 0
    for item, amt, dt, cat in rows:
        text += f"• {dt} | {item} — {amt:,.0f} so'm\n"
        total += amt
    text += f"\n━━━━━━━━━━\n💰 **Jami: {total:,.0f} so'm**"
    await callback.message.edit_text(text, parse_mode="Markdown")

@user_router.callback_query(F.data == "search_date_prompt")
async def callback_search_date_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSM.search_date)
    await callback.message.answer("📅 Sanani kiriting (Format: `YYYY-MM-DD`, masalan: `2026-07-25`):", parse_mode="Markdown")
    await callback.answer()

@user_router.message(F.state == FSM.search_date, F.text)
async def process_search_by_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name, e.item_name, e.amount, e.time 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.date = ?
    """, (user_id, date_str))
    rows = cursor.fetchall()
    conn.close()
    
    await state.clear()
    if not rows:
        await message.answer(f"🤷‍♂️ {date_str} sanasida hech qanday xarajat topilmadi.")
        return
        
    text = f"📅 **{date_str} sanasidagi xarajatlar:**\n\n"
    total = 0
    for cat, item, amt, tm in rows:
        text += f"• [{tm}] {cat}: {item} — {amt:,.0f} so'm\n"
        total += amt
    text += f"\n━━━━━━━━━━\n💰 **Jami: {total:,.0f} so'm**"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu(message))

# ================= ERKIN MATN ORQALI XARAJAT QO'SHISH =================
@user_router.message(F.text)
async def process_expense_input(message: types.Message, state: FSMContext):
    await state.clear()
    if message.text.startswith('/'):
        return
    text = message.text.strip()
    parsed_items = parse_expense_text(text)
    if not parsed_items:
        return
        
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    user_id = message.from_user.id
    add_user(user_id)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total_sum = 0
    response_text = f"✅ Saqlandi!\n\n"
    
    for item in parsed_items:
        item_name = item['item_name']
        amount = item['amount']
        category_name = item['category']
        
        cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
        row = cursor.fetchone()
        if row:
            category_id = row[0]
        else:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
            category_id = cursor.lastrowid
            
        cursor.execute('INSERT INTO expenses (user_id, amount, category_id, item_name, date, time) VALUES (?, ?, ?, ?, ?, ?)', 
                       (user_id, amount, category_id, item_name, now.strftime("%Y-%m-%d"), now.strftime("%H:%M")))
        total_sum += amount
        response_text += f"🔹 {item_name} — {amount:,.0f} so'm ({category_name})\n"
        
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (total_sum, user_id))
    conn.commit()
    conn.close()
    
    balance = get_balance(user_id)
    response_text += f"\n━━━━━━━━━━\n💰 **Jami: {total_sum:,.0f} so'm**\n💳 **Balans: {balance:,.0f} so'm**"
    await message.answer(response_text, parse_mode="Markdown")
