import logging
import sqlite3
import asyncio
import re
from datetime import datetime, timedelta
import pytz
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aiogram import Router, F, Bot, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# Fayl tuzilmangizga mos ravishda chaqirasiz (parse_expense_text endi kerak emas, o'zimiz yozdik)
from app.database.db import DB_PATH, add_user, update_balance, get_balance, get_user_lang, set_user_lang
from app.keyboards.reply import get_main_menu, get_settings_menu
from config import TIMEZONE

user_router = Router()

class FSM(StatesGroup):
    income = State()
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
        f"Salom, {message.from_user.full_name}! 👋\n\n🤖 Men sizning aqlli moliyaviy botingizman.\n"
        f"💳 Joriy balans: **{balance:,.0f} so'm**\n\n"
        f"💡 Xarajat qo'shish uchun shunchaki menga matn yuboring:\n"
        f"Masalan: \n`Non 4 ta 3000`\n`Shakar 1.5kg 20000`\n`Kola 15000`",
        reply_markup=get_main_menu(message),
        parse_mode="Markdown"
    )

@user_router.message(F.text.in_({"⚙️ Sozlamalar", "⚙️ Настройки", "⚙️ Settings", "/settings"}))
async def process_settings(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Sozlamalar bo'limi:", reply_markup=get_settings_menu(message))

@user_router.message(F.text.in_({"🇺🇿 O'zbekcha", "🇷🇺 Русский", "🇬🇧 English"}))
async def change_language(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if "O'zbekcha" in message.text: set_user_lang(user_id, 'uz')
    elif "Русский" in message.text: set_user_lang(user_id, 'ru')
    elif "English" in message.text: set_user_lang(user_id, 'en')
    await message.answer("✅ Til o'zgartirildi!", reply_markup=get_main_menu(message))

@user_router.message(F.text.in_({"⬅️ Ortga", "⬅️ Назад", "⬅️ Back"}))
async def process_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu", reply_markup=get_main_menu(message))

# ================= DAROMAD KIRITISH =================
@user_router.message(F.text.in_({"➕ Daromad kiritish", "➕ Добавить доход", "➕ Add Income"}))
async def process_income_btn(message: types.Message, state: FSMContext):
    await state.set_state(FSM.income)
    await message.answer("💰 Daromad summasini kiriting (masalan: `15 000 000`):", 
                         reply_markup=get_cancel_kb(), parse_mode="Markdown")

@user_router.message(F.state == FSM.income, F.text)
async def process_income_amount(message: types.Message, state: FSMContext):
    text = message.text.strip().replace(" ", "").replace(",", ".")
    if not text.replace('.', '', 1).isdigit():
        await message.answer("❌ Noto'g'ri qiymat. Faqat raqam kiriting:", reply_markup=get_cancel_kb())
        return
        
    amount = float(text)
    if amount <= 0:
        await message.answer("❌ Summa 0 dan katta bo'lishi kerak:", reply_markup=get_cancel_kb())
        return
        
    user_id = message.from_user.id
    update_balance(user_id, amount)
    balance = get_balance(user_id)
    await state.clear()
    
    undo_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Oxirgi kirimni o'chirish", callback_data=f"undo_inc_{amount}")]
    ])
    await message.answer(f"✅ Hisobingizga **{amount:,.0f} so'm** qo'shildi!\n💳 Joriy balans: **{balance:,.0f} so'm**",
                         reply_markup=undo_kb, parse_mode="Markdown")

@user_router.callback_query(F.data.startswith("undo_inc_"))
async def undo_income_callback(callback: types.CallbackQuery):
    amount = float(callback.data.split("_")[2])
    user_id = callback.from_user.id
    update_balance(user_id, -amount)
    new_balance = get_balance(user_id)
    await callback.message.edit_text(f"🗑 Kiritilgan **{amount:,.0f} so'm** bekor qilindi!\n💳 Joriy balans: **{new_balance:,.0f} so'm**", parse_mode="Markdown")
    await callback.answer("O'chirildi!")

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
        await message.answer(f"✅ '{cat_name}' qo'shildi!", reply_markup=get_main_menu(message))
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
    
    keyboard = [[InlineKeyboardButton(text=f"❌ {name}", callback_data=f"delcat_{cat_id}")] for cat_id, name in rows]
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
        cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        await callback.message.edit_text(f"🗑 '{row[0]}' o'chirildi!")
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
        SELECT c.name, SUM(e.amount) FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? GROUP BY c.name
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("🤷‍♂️ Diagramma uchun xarajatlar yo'q.")
        return
        
    categories, amounts = [r[0] for r in rows], [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    ax.axis('equal')
    ax.set_title("Xarajatlar taqsimoti")
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    plt.close(fig)
    await message.answer_photo(BufferedInputFile(buffer.getvalue(), "chart.png"), caption="📊 Umumiy diagrammangiz:")

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
    keyboard = [[InlineKeyboardButton(text=name, callback_data=f"schcat_{cat_id}")] for cat_id, name in cursor.fetchall()]
    conn.close()
    await callback.message.edit_text("🔍 Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@user_router.callback_query(F.data.startswith("schcat_"))
async def callback_search_by_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.item_name, e.amount, e.date FROM expenses e
        WHERE e.user_id = ? AND e.category_id = ? ORDER BY e.date DESC
    """, (callback.from_user.id, cat_id))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.edit_text("🤷‍♂️ Xarajatlar topilmadi.")
        return
        
    text = "📂 **Qidiruv natijasi:**\n\n"
    total = 0
    for item, amt, dt in rows:
        text += f"• {dt} | {item} — {amt:,.0f} so'm\n"
        total += amt
    await callback.message.edit_text(f"{text}\n💰 **Jami: {total:,.0f} so'm**", parse_mode="Markdown")

@user_router.callback_query(F.data == "search_date_prompt")
async def callback_search_date_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSM.search_date)
    await callback.message.answer("📅 Sanani kiriting (`YYYY-MM-DD`, masalan: `2026-07-25`):", parse_mode="Markdown")

@user_router.message(F.state == FSM.search_date, F.text)
async def process_search_by_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name, e.item_name, e.amount, e.time FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND e.date = ?
    """, (message.from_user.id, date_str))
    rows = cursor.fetchall()
    conn.close()
    
    await state.clear()
    if not rows:
        await message.answer(f"🤷‍♂️ {date_str} sanasida xarajat topilmadi.")
        return
        
    text = f"📅 **{date_str} xarajatlari:**\n\n"
    total = 0
    for cat, item, amt, tm in rows:
        text += f"• [{tm}] {cat}: {item} — {amt:,.0f} so'm\n"
        total += amt
    await message.answer(f"{text}\n💰 **Jami: {total:,.0f} so'm**", parse_mode="Markdown")

# ================= AQLLI XARAJAT PARSERI VA KATEGORIYA =================

# Agar kimdir eski knopkani bosib qolsa, ogohlantiramiz
@user_router.message(F.text.in_({"➕ Xarajat kiritish", "➕ Добавить расход", "➕ Add Expense"}))
async def process_expense_btn_old(message: types.Message):
    await message.answer("💡 Endi xarajatlarni to'g'ridan-to'g'ri menga SMS qilib yozing!\n\nMasalan:\n`Non 4 ta 3000`\n`Shakar 1kg 20000`\n`Kola 20000`", parse_mode="Markdown")

def get_auto_category(item_name: str, cursor, user_id: int) -> int:
    # 1. Avval foydalanuvchining o'z tarixidan qidiradi
    cursor.execute("""
        SELECT category_id FROM expenses 
        WHERE item_name LIKE ? AND user_id = ? 
        ORDER BY date DESC, time DESC LIMIT 1
    """, (f"%{item_name}%", user_id))
    row = cursor.fetchone()
    if row: return row[0]
    
    # 2. Topilmasa lug'at orqali aniqlaydi
    text = item_name.lower()
    cat_name = "Boshqalar"
    if any(w in text for w in ['non', 'shakar', 'tuz', 'yog', 'go\'sht', 'gosht', 'tuxum', 'un', 'makaron', 'choy', 'qahva', 'kartoshka', 'piyoz']):
        cat_name = "Oziq-ovqat"
    elif any(w in text for w in ['kola', 'pepsi', 'fanta', 'suv', 'sok', 'sharbat', 'ichimlik']):
        cat_name = "Ichimliklar"
    elif any(w in text for w in ['dor', 'tabletka', 'ukol', 'krem', 'maz', 'shifokor']):
        cat_name = "Tibbiyot"
    elif any(w in text for w in ['benzin', 'gaz', 'moy', 'zapchast', 'taksi', 'avto', 'mashina']):
        cat_name = "Transport"
    
    # Kategoriya bazada bormi?
    cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_name,))
    cat_row = cursor.fetchone()
    if cat_row: return cat_row[0]
    
    # Yo'q bo'lsa yangi yaratadi
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
    return cursor.lastrowid

@user_router.message(F.text)
async def process_smart_expense(message: types.Message, state: FSMContext):
    if message.text.startswith('/'): return
    
    ignore_list = ["⚙️ Sozlamalar", "🇺🇿 O'zbekcha", "🇷🇺 Русский", "🇬🇧 English", "⬅️ Ortga", "📊 Diagramma", "🔍 Qidiruv", "📂 Kategoriyalar"]
    if message.text in ignore_list: return
        
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    user_id = message.from_user.id
    add_user(user_id)
    
    lines = message.text.strip().split('\n')
    pattern = re.compile(r"^(.*?)(?:\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr|metr|m))?\s+([\d\s\.,]+)$", re.IGNORECASE)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_sum = 0
    inserted_ids = []
    response_text = "✅ Saqlandi!\n\n"
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = pattern.match(line)
        if match:
            item_name = match.group(1).strip()
            if not item_name: continue
            
            qty_str, unit, price_str = match.group(2), match.group(3), match.group(4)
            price_str = price_str.replace(" ", "").replace(",", ".")
            
            try:
                price = float(price_str)
                if qty_str and unit:
                    qty = float(qty_str)
                    amount = price * qty
                    display_name = f"{item_name} {qty_str}{unit}"
                else:
                    amount = price
                    display_name = item_name
                
                cat_id = get_auto_category(item_name, cursor, user_id)
                cursor.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
                cat_name = cursor.fetchone()[0]
                
                cursor.execute('''
                    INSERT INTO expenses (user_id, amount, category_id, item_name, date, time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, amount, cat_id, display_name, now.strftime("%Y-%m-%d"), now.strftime("%H:%M")))
                
                inserted_ids.append(cursor.lastrowid)
                total_sum += amount
                response_text += f"🔹 {display_name} — {amount:,.0f} so'm ({cat_name})\n"
            except ValueError:
                continue

    if inserted_ids:
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (total_sum, user_id))
        conn.commit()
        
        balance = get_balance(user_id)
        response_text += f"\n━━━━━━━━━━\n💰 **Jami: {total_sum:,.0f} so'm**\n💳 **Balans: {balance:,.0f} so'm**"
        
        start_id, end_id = min(inserted_ids), max(inserted_ids)
        undo_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Oxirgi xarajatni o'chirish", callback_data=f"undo_batch_{start_id}_{end_id}_{total_sum}")]
        ])
        await message.answer(response_text, reply_markup=undo_kb, parse_mode="Markdown")
    else:
        # Agar bot matnni umuman tushunmasa
        await message.answer("⚠️ Kechirasiz, matnni tushuna olmadim. Iltimos, quyidagicha formatda kiriting:\n\n`Non 4 ta 3000`\n`Kola 15000`", parse_mode="Markdown")
        
    conn.close()
    await state.clear()

@user_router.callback_query(F.data.startswith("undo_batch_"))
async def undo_batch_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    start_id = int(parts[2])
    end_id = int(parts[3])
    total_sum = float(parts[4])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id >= ? AND id <= ? AND user_id = ?", (start_id, end_id, user_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_sum, user_id))
    conn.commit()
    conn.close()
    
    new_balance = get_balance(user_id)
    await callback.message.edit_text(
        f"🗑 Yozilgan xarajatlar bekor qilindi va pul balansga qaytarildi!\n💳 Joriy balans: **{new_balance:,.0f} so'm**", 
        parse_mode="Markdown"
    )
    await callback.answer("Muvaffaqiyatli o'chirildi!")
