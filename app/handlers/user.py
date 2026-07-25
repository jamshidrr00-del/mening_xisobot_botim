import logging
import sqlite3
from datetime import datetime
import pytz

from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.keyboards.reply import get_settings_menu
from app.services.parser import parse_expense_text
from config import TIMEZONE
from app.database.db import DB_PATH, add_user, update_balance, get_balance

user_router = Router()

# Kirim kiritish uchun holatlar (FSM)
class IncomeStates(StatesGroup):
    waiting_for_amount = State()

# Yordamchi funksiya: kategoriya nomidan uning ID sini olish yoki bazaga qo'shib ID qaytarish
def get_or_create_category_id(cursor, category_name):
    cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
    return cursor.lastrowid

# ==========================================
# 1. ASOSIY BUYRUQLAR VA MENYU (Start)
# ==========================================
@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    add_user(user_id)
    current_balance = get_balance(user_id)

    # Doimiy pastki menyuni yaratamiz
    main_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="🗑 Tozalash")],
            [KeyboardButton(text="➕ Daromad kiritish"), KeyboardButton(text="⚙️ Sozlamalar")]
        ],
        resize_keyboard=True
    )

    welcome_text = (
        f"Salom, {full_name}! 👋\n\n"
        f"🤖 **Men sizning shaxsiy moliyaviy yordamchingizman.**\n\n"
        f"❓ **Bu bot nima qiladi va nima uchun kerak?**\n"
        f"Bot orqali siz kunlik xarajatlaringizni tez va oson nazorat qilishingiz mumkin. "
        f"Qog'oz yoki murakkab dasturlarni unuting! Barchasini shu yerda, oddiy xabarlar orqali yozib boring va o'z byudjetingizni boshqaring.\n\n"
        f"👥 *Eslatma:* Har bir foydalanuvchi o'zining shaxsiy hisoboti va balansiga ega. Botni do'stlaringizga ham ulashishingiz mumkin — ularning ma'lumotlari sizdan to'liq alohida saqlanadi.\n\n"
        f"💡 **Qanday foydalaniladi?**\n"
        f"1️⃣ **Xarajat kiritish:** Shunchaki xarajat nomi va summani yozib yuboring (Masalan: `Non 18000`).\n"
        f"2️⃣ **Daromad qo'shish:** `/kirim` buyrug'i yoki tugma orqali summani kiriting.\n"
        f"3️⃣ **Hisobot ko'rish:** 📊 Hisobot tugmasi orqali kunlik tahlilni ko'ring.\n\n"
        f"💳 **Sizning joriy balansingiz:** **{current_balance:,.0f} so'm**"
    )

    await message.answer(
        welcome_text,
        reply_markup=main_menu,
        parse_mode="Markdown"
    )

# ==========================================
# 2. DAROMAD (KIRIM) BO'LIMI (Interaktiv)
# ==========================================
@user_router.message(F.text == "➕ Daromad kiritish")
async def process_income_btn(message: types.Message, state: FSMContext):
    await state.set_state(IncomeStates.waiting_for_amount)
    await message.answer(
        "💰 Iltimos, qo'shiladigan summani kiriting (masalan: `150000`):",
        parse_mode="Markdown"
    )

@user_router.message(Command("kirim"))
async def cmd_kirim(message: types.Message, state: FSMContext):
    await state.set_state(IncomeStates.waiting_for_amount)
    await message.answer(
        "💰 Iltimos, qo'shiladigan summani kiriting (masalan: `150000`):",
        parse_mode="Markdown"
    )

# Foydalanuvchi kiritgan summani qabul qilish
@user_router.message(IncomeStates.waiting_for_amount, F.text)
async def process_income_amount(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return

    text = message.text.strip()
    
    # 📌 Matn orasidagi bo'shliqlarni olib tashlaymiz 
    # (Masalan: "15 000 000" -> "15000000")
    cleaned_text = text.replace(" ", "")
    
    if not cleaned_text.isdigit():
        await message.answer(
            "⚠️ Iltimos, faqat raqamlardan iborat summani kiriting!\n"
            "Namuna formatlar:\n"
            "• `15000000`\n"
            "• `15 000 000`", 
            parse_mode="Markdown"
        )
        return
    
    amount = float(cleaned_text)
    user_id = message.from_user.id
    add_user(user_id)
    update_balance(user_id, amount)
    current_balance = get_balance(user_id)
    
    await state.clear()
    
    # Xato yozilsa, darhol bekor qilish imkonini beruvchi tugma
    undo_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Bekor qilish (Xato yozdim)", callback_data=f"undo_kirim_{amount}")]
    ])
    
    await message.answer(
        f"✅ Hisobingizga **{amount:,.0f} so'm** qo'shildi!\n"
        f"💳 Joriy balans: **{current_balance:,.0f} so'm**",
        reply_markup=undo_keyboard,
        parse_mode="Markdown"
    )

# Kirimni bekor qilish tugmasi bosilganda ishlaydigan funksiya
@user_router.callback_query(F.data.startswith("undo_kirim_"))
async def undo_kirim_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    amount = float(callback.data.split("_")[2])
    
    update_balance(user_id, -amount)
    current_balance = get_balance(user_id)
    
    await callback.message.edit_text(
        f"🗑 **Kirim bekor qilindi!** (-{amount:,.0f} so'm)\n"
        f"💳 Qolgan balans: **{current_balance:,.0f} so'm**",
        parse_mode="Markdown"
    )
    await callback.answer("Bekor qilindi!")

# ==========================================
# 3. BOSHQA MENYU TUGMALARI (Sozlamalar, Ortga)
# ==========================================
@user_router.message(F.text.in_({"⚙️ Sozlamalar", "/settings"}))
async def process_settings(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Sozlamalar bo'limidasiz. Nima o'zgartiramiz?", reply_markup=get_settings_menu())

@user_router.message(F.text == "⬅️ Ortga")
async def process_back(message: types.Message, state: FSMContext):
    await state.clear()
    main_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="🗑 Tozalash")],
            [KeyboardButton(text="➕ Daromad kiritish"), KeyboardButton(text="⚙️ Sozlamalar")]
        ],
        resize_keyboard=True
    )
    await message.answer("Asosiy menyuga qaytdik 🏠", reply_markup=main_menu)

# ==========================================
# 4. HISOBOT VA XARAJATNI TOZALASH
# ==========================================
@user_router.message(F.text.in_({"📊 Hisobot", "/report"}))
async def process_report(message: types.Message, state: FSMContext):
    await state.clear()
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

@user_router.message(F.text.in_({"🗑 Tozalash", "/undo"}))
async def process_undo_last(message: types.Message, state: FSMContext):
    await state.clear()
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

# ==========================================
# 5. ASOSIY XARAJAT QABUL QILUVCHI HANDLER
# ==========================================
@user_router.message(F.text)
async def process_expense_input(message: types.Message, state: FSMContext):
    await state.clear()
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
