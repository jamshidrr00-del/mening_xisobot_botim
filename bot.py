import asyncio
import logging
import os
import re
import threading
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from flask import Flask

# DB faylidan funksiyalarni import qilish (get_connection qo'shildi)
from app.database.db import (
    init_db,
    add_user,
    update_balance,
    get_balance,
    add_expense,
    add_category,
    get_categories,
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
        BotCommand(command="tozalash", description="Oxirgi xarajatni o'chirish 🗑"),
        BotCommand(command="kunlik", description="Kunlik hisobot 📊")
    ]
    await bot.set_my_commands(commands)

# --- STANDART KATEGORIYA YARATISH ---
def seed_default_category():
    add_category("Umumiy")

# ================= 1. KIRIM (DAROMAD) QISMI =================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id)
    current_balance = get_balance(user_id)
    await message.answer(
        f"Assalomu alaykum! Xarajatlarni hisoblab boruvchi botga xush kelibsiz. 🚀\n\n"
        f"💳 Joriy balansingiz: {current_balance:,.0f} so'm\n\n"
        f"Xarajatlarni yozish uchun shunchaki quyidagi formatda yuboring:\n"
        f"<code>non 4 ta 3000</code>\n"
        f"<code>shakar 2 kg 10000</code>",
        parse_mode="HTML"
    )

@router.message(Command("kirim"))
async def cmd_kirim(message: types.Message, state: FSMContext):
    await message.answer("💰 Balansga qo'shmoqchi bo'lgan summani kiriting (masalan: 1 500 000):")
    await state.set_state(FSM.income)

@router.message(F.state == FSM.income, F.text)
async def process_income(message: types.Message, state: FSMContext):
    text = re.sub(r'\s+', '', message.text)

    if text.isdigit():
        amount = float(text)
        user_id = message.from_user.id
        
        add_user(user_id)
        update_balance(user_id, amount)
        current_balance = get_balance(user_id)

        # Bekor qilish tugmasi FAQAT kirim uchun qoldi
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Oxirgi kirimni o'chirish", callback_data=f"undo_inc_{int(amount)}")]
        ])

        await message.answer(
            f"✅ Balansga {amount:,.0f} so'm qo'shildi.\n💳 Joriy balans: {current_balance:,.0f} so'm",
            reply_markup=kb
        )
        await state.clear()
    else:
        await message.answer("❌ Noto'g'ri summa kiritildi. Iltimos, faqat raqam kiriting:")

@router.callback_query(F.data.startswith("undo_inc_"))
async def undo_income(callback: types.CallbackQuery):
    amount = float(callback.data.split("_")[2])
    user_id = callback.from_user.id

    update_balance(user_id, -amount)
    current_balance = get_balance(user_id)

    await callback.message.edit_text(
        f"🗑 {amount:,.0f} so'm kirim bekor qilindi.\n💳 Joriy balans: {current_balance:,.0f} so'm"
    )
    await callback.answer("Kirim o'chirildi")


# ================= 2. MENYU BUYRUQLARI (TOZALASH VA KUNLIK) =================

@router.message(Command("tozalash"))
async def cmd_tozalash(message: types.Message):
    user_id = message.from_user.id
    
    # Ma'lumotlar bazasiga bevosita ulanib, eng oxirgi xarajatni topamiz
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, amount, item_name FROM expenses 
        WHERE user_id = ? ORDER BY id DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    
    if row:
        exp_id, amount, item_name = row
        # 1. Baza yozuvidan o'chirish
        cursor.execute('DELETE FROM expenses WHERE id = ?', (exp_id,))
        # 2. Pulni foydalanuvchi balansiga qaytarish
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
        SELECT item_name, amount, time FROM expenses 
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"📅 <b>{today}</b>\n\nBugun uchun xarajatlar yo'q. 🤷‍♂️", parse_mode="HTML")
        return
        
    total = sum(row[1] for row in rows)
    report_lines = [f"📊 <b>Bugungi xarajatlar ({today}):</b>\n"]
    
    for row in rows:
        report_lines.append(f"🔹 {row[0]} — {int(row[1]):,} so'm ({row[2]})")
    
    report_lines.append(f"\n💰 <b>Jami kunlik xarajat: {int(total):,} so'm</b>")
    await message.answer("\n".join(report_lines), parse_mode="HTML")


# ================= 3. XARAJAT QISMI (YANGI FORMATDA) =================

@router.message(F.text)
async def process_expense(message: types.Message):
    if message.text.startswith('/'):
        return

    user_id = message.from_user.id
    add_user(user_id)
    lines = message.text.strip().split('\n')

    pattern = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr|m|metr)\s+([\d\s]+)$", re.IGNORECASE)

    response_blocks = []
    total_expense = 0
    
    tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    categories = get_categories()
    default_cat_id = categories[0][0] if categories else 1

    for line in lines:
        match = pattern.match(line.strip())
        if match:
            name = match.group(1).strip().capitalize()
            qty_str = match.group(2)
            qty = float(qty_str) if '.' in qty_str else int(qty_str)
            unit = match.group(3).strip().lower()

            price_str = match.group(4)
            price = float(re.sub(r'\s+', '', price_str))

            line_total = qty * price
            total_expense += line_total

            item_full_name = f"{name} {qty} {unit}"
            
            add_expense(
                user_id=user_id,
                amount=line_total,
                category_id=default_cat_id,
                item_name=item_full_name,
                date=date_str,
                time=time_str
            )

            # Siz so'ragan yangi dizayndagi xarajat formati
            block = (
                f"📝 Nomi: {item_full_name}\n"
                f"💰 Summa: {int(line_total):,} so'm\n"
                f"🗂 Kategoriya: 🎁 Boshqa\n"
                f"📅 Vaqt: {date_str} {time_str}"
            )
            response_blocks.append(block)

    if response_blocks:
        current_balance = get_balance(user_id)
        
        # Bloklarni orasini ochiq qilib birlashtiramiz
        final_text = "\n\n".join(response_blocks)
        final_text += f"\n\n💳 Joriy balans: {current_balance:,.0f} so'm"

        # TUGMA OLIB TASHLANDI: Endi bekor qilish uchun menyudagi /tozalash ishlatiladi
        await message.answer(final_text)
    else:
        await message.answer(
            "⚠️ Xarajatni quyidagi formatda yuboring:\n\n"
            "gril 4 ta 62000\n"
            "shakar 2 kg 10000"
        )


# ================= ASOSIY ISHGA TUSHIRISH =================

async def main():
    init_db()
    seed_default_category()

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
