import asyncio
import logging
import os
import re
import sqlite3
import threading
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask

# --- 1. FLASK SERVER (Render 24/7 ishlashi uchun) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is active!"


def run_flask():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


# --- 2. BAZA BILAN ISHLASH (SQLite) ---
DB_PATH = "database.db"


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0
        )
    """)
  conn.commit()
  conn.close()


def add_user(user_id):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,)
  )
  conn.commit()
  conn.close()


def update_balance(user_id, amount):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET balance = balance + ? WHERE user_id = ?",
      (amount, user_id),
  )
  conn.commit()
  conn.close()


def get_balance(user_id):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  conn.close()
  return row[0] if row else 0


# --- 3. BOT SOZLAMALARI ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
  raise ValueError("BOT_TOKEN topilmadi! Render Environment'ga qo'shing.")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()


class FSM(StatesGroup):
  income = State()


# ================= KIRIM (DAROMAD) QISMI =================


@router.message(Command("kirim"))
async def cmd_kirim(message: types.Message, state: FSMContext):
  await message.answer(
      "💰 Balansga qo'shmoqchi bo'lgan summani kiriting (masalan: 1500000 yoki 15"
      " 000 000):"
  )
  await state.set_state(FSM.income)


@router.message(F.state == FSM.income, F.text)
async def process_income(message: types.Message, state: FSMContext):
  text = re.sub(r"\s+", "", message.text)

  if text.isdigit():
    amount = int(text)
    user_id = message.from_user.id
    add_user(user_id)

    update_balance(user_id, amount)
    current_balance = get_balance(user_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🗑 Oxirgi kirimni o'chirish", callback_data=f"undo_inc_{amount}"
        )
    ]])

    await message.answer(
        f"✅ Balansga {amount:,.0f} so'm qo'shildi.\n💳 Joriy balans:"
        f" {current_balance:,.0f} so'm",
        reply_markup=kb,
    )
    await state.clear()
  else:
    await message.answer(
        "❌ Noto'g'ri summa kiritildi. Iltimos, faqat raqam kiriting:"
    )


@router.callback_query(F.data.startswith("undo_inc_"))
async def undo_income(callback: types.CallbackQuery):
  amount = int(callback.data.split("_")[2])
  user_id = callback.from_user.id

  update_balance(user_id, -amount)
  current_balance = get_balance(user_id)

  await callback.message.edit_text(
      f"🗑 {amount:,.0f} so'm kirim bekor qilindi.\n💳 Joriy balans:"
      f" {current_balance:,.0f} so'm"
  )
  await callback.answer("Kirim o'chirildi")


# ================= XARAJAT QISMI (BUYRUQLARSIZ) =================


@router.message(F.text)
async def process_expense(message: types.Message):
  if message.text.startswith("/"):
    return

  user_id = message.from_user.id
  add_user(user_id)
  lines = message.text.strip().split("\n")

  pattern = re.compile(
      r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr|m|metr)\s+([\d\s]+)$",
      re.IGNORECASE,
  )

  response_lines = []
  total_expense = 0

  for line in lines:
    match = pattern.match(line.strip())
    if match:
      name = match.group(1).strip().capitalize()
      qty_str = match.group(2)
      qty = float(qty_str) if "." in qty_str else int(qty_str)
      unit = match.group(3).strip().lower()

      price_str = match.group(4)
      price = int(re.sub(r"\s+", "", price_str))

      line_total = qty * price
      total_expense += line_total

      response_lines.append(f"✅ {name} {qty} {unit} {int(line_total)} so'm")

  if response_lines:
    update_balance(user_id, -total_expense)
    current_balance = get_balance(user_id)

    final_text = "\n".join(response_lines)
    final_text += f"\n\n💳 Joriy balans: {current_balance:,.0f} so'm"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🗑 Xarajatni bekor qilish",
            callback_data=f"undo_exp_{total_expense}",
        )
    ]])

    await message.answer(final_text, reply_markup=kb)
  else:
    await message.answer(
        "⚠️ Iltimos, xarajatni quyidagi formatda kiriting:\n\nnon 4 ta"
        " 3000\nshakar 2 kg 10000"
    )


@router.callback_query(F.data.startswith("undo_exp_"))
async def undo_expense(callback: types.CallbackQuery):
  amount = int(callback.data.split("_")[2])
  user_id = callback.from_user.id

  update_balance(user_id, amount)
  current_balance = get_balance(user_id)

  await callback.message.edit_text(
      f"🗑 Xarajat bekor qilindi va {amount:,.0f} so'm balansga qaytarildi.\n💳"
      f" Joriy balans: {current_balance:,.0f} so'm"
  )
  await callback.answer("Xarajat bekor qilindi")


# ================= ASOSIY ISHGA TUSHIRISH QISMI =================


async def main():
  init_db()
  threading.Thread(target=run_flask, daemon=True).start()

  dp.include_router(router)
  await bot.delete_webhook(drop_pending_updates=True)
  logging.info("Bot ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  try:
    asyncio.run(main())
  except (KeyboardInterrupt, SystemExit):
    logging.info("Bot to'xtatildi.")
