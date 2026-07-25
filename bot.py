import asyncio
from datetime import datetime, timedelta
import logging
import sqlite3
import threading

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from flask import Flask

# --- SOZLAMALAR VA LOGLAR ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

TOKEN = "8522306001:AAFNLspuu9QEX0wCGvzohK69Bf2qietscXQ"
PORT = 8080  # Render yoki boshqa hostlar uchun port
DB_PATH = "bot_database.db"

# --- FLASK SERVER (24/7 ishlashi uchun) ---
app = Flask(__name__)


@app.route("/")
def index():
  return "Expense Tracker Bot is running 24/7! 🚀"


def run_flask():
  """Flask serverni alohida oqimda (thread) yurgizish"""
  app.run(host="0.0.0.0", port=PORT)


# --- AIOGRAM BOT VA ROUTER ---
router = Router()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- BAZA BILAN ISHLASH ---
def get_connection():
  return sqlite3.connect(DB_PATH)


def init_db():
  conn = get_connection()
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            language TEXT DEFAULT 'uz',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            category_id INTEGER,
            item_name TEXT,
            date TEXT,
            time TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)
  conn.commit()
  conn.close()


def seed_categories():
  init_db()
  conn = get_connection()
  cursor = conn.cursor()
  default_cats = [
      "🍔 Oziq-ovqat",
      "🚗 Transport",
      "💡 Kommunal",
      "🛍 Xaridlar",
      "📌 Boshqa",
  ]
  for cat in default_cats:
    try:
      cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
    except sqlite3.IntegrityError:
      pass
  conn.commit()
  conn.close()


# --- FSM HOLATLARI ---
class ExpenseState(StatesGroup):
  waiting_for_amount = State()
  waiting_for_category = State()
  waiting_for_item_name = State()


class IncomeState(StatesGroup):
  waiting_for_amount = State()


# --- /START BUYRUQI ---
@router.message(CommandStart())
async def cmd_start(message: Message):
  user_id = message.from_user.id
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)",
      (user_id, 0.0),
  )
  conn.commit()
  conn.close()

  text = (
      f"Assalomu alaykum, {message.from_user.first_name}!\n\n"
      "Bu moliyaviy hisob-kitob boti. Quyidagi buyruqlar orqali"
      " boshqarishingiz mumkin:\n\n"
      "➕ /kirim - Balansga pul qo'shish\n"
      "💸 /xarajat - Xarajat qo'shish\n"
      "📊 /report - Umumiy hisobot\n"
      "📅 /weekly - Haftalik hisobot\n"
      "📈 /monthly - Oylik hisobot\n"
      "↩️ /undo - Oxirgi xarajatni bekor qilish\n"
      "⚙️ /settings - Sozlamalar"
  )
  await message.answer(text)


# --- /KIRIM (Balansni to'ldirish) ---
@router.message(Command("kirim"))
async def cmd_kirim(message: Message, state: FSMContext):
  await message.answer(
      "💳 Balansingizga qo'shmoqchi bo'lgan summani kiriting (masalan:"
      " `150000`):",
      parse_mode="Markdown",
  )
  await state.set_state(IncomeState.waiting_for_amount)


@router.message(IncomeState.waiting_for_amount)
async def process_income(message: Message, state: FSMContext):
  try:
    amount = float(message.text.replace(",", "."))
    if amount <= 0:
      raise ValueError
  except ValueError:
    await message.answer("❌ Noto'g'ri qiymat. Faqat raqam kiriting:")
    return

  user_id = message.from_user.id
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET balance = balance + ? WHERE user_id = ?",
      (amount, user_id),
  )
  cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
  new_balance = cursor.fetchone()[0]
  conn.commit()
  conn.close()

  await state.clear()
  await message.answer(
      f"✅ Hisobingiz to'ldirildi!\n💰 Qo'shildi: `{amount:,.2f}` so'm\n💳 Joriy"
      f" balans: `{new_balance:,.2f}` so'm",
      parse_mode="Markdown",
  )


# --- XARAJAT QO'SHISH ---
@router.message(Command("xarajat"))
async def cmd_xarajat(message: Message, state: FSMContext):
  await message.answer("💸 Xarajat summasini kiriting:")
  await state.set_state(ExpenseState.waiting_for_amount)


@router.message(ExpenseState.waiting_for_amount)
async def exp_amount(message: Message, state: FSMContext):
  try:
    amount = float(message.text.replace(",", "."))
    if amount <= 0:
      raise ValueError
  except ValueError:
    await message.answer("❌ Xato summa. Qaytadan kiriting:")
    return

  await state.update_data(amount=amount)

  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT id, name FROM categories")
  categories = cursor.fetchall()
  conn.close()

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text=name, callback_data=f"expcat_{cat_id}")]
          for cat_id, name in categories
      ]
  )
  await message.answer("📂 Xarajat kategoriyasini tanlang:", reply_markup=keyboard)
  await state.set_state(ExpenseState.waiting_for_category)


@router.callback_query(
    ExpenseState.waiting_for_category, F.data.startswith("expcat_")
)
async def exp_category(callback: CallbackQuery, state: FSMContext):
  cat_id = int(callback.data.split("_")[1])
  await state.update_data(category_id=cat_id)
  await callback.message.edit_text(
      "💬 Xarajat bo'yicha izoh (nima uchun qilinganini) yozing:"
  )
  await state.set_state(ExpenseState.waiting_for_item_name)
  await callback.answer()


@router.message(ExpenseState.waiting_for_item_name)
async def exp_finish(message: Message, state: FSMContext):
  item_name = message.text
  data = await state.get_data()
  amount = data.get("amount")
  category_id = data.get("category_id")
  user_id = message.from_user.id

  now = datetime.now()
  date_str = now.strftime("%Y-%m-%d")
  time_str = now.strftime("%H:%M")

  conn = get_connection()
  cursor = conn.cursor()

  cursor.execute(
      """
        INSERT INTO expenses (user_id, amount, category_id, item_name, date, time)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (user_id, amount, category_id, item_name, date_str, time_str),
  )
  cursor.execute(
      "UPDATE users SET balance = balance - ? WHERE user_id = ?",
      (amount, user_id),
  )
  conn.commit()
  conn.close()

  await state.clear()
  await message.answer(
      "✅ Xarajat muvaffaqiyatli saqlandi!\n"
      f"💵 Summa: `{amount:,.2f}` so'm\n"
      f"📝 Izoh: {item_name}",
      parse_mode="Markdown",
  )


# --- /REPORT (Umumiy hisobot) ---
@router.message(Command("report"))
async def cmd_report(message: Message):
  user_id = message.from_user.id
  conn = get_connection()
  cursor = conn.cursor()

  cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
  res = cursor.fetchone()
  balance = res[0] if res else 0.0

  cursor.execute(
      "SELECT SUM(amount) FROM expenses WHERE user_id = ?", (user_id,)
  )
  total_exp = cursor.fetchone()[0] or 0.0

  cursor.execute(
      """
        SELECT c.name, SUM(e.amount) 
        FROM expenses e 
        JOIN categories c ON e.category_id = c.id 
        WHERE e.user_id = ? 
        GROUP BY c.name
    """,
      (user_id,),
  )
  cats = cursor.fetchall()
  conn.close()

  text = (
      f"📊 *Umumiy moliyaviy hisobot*\n\n💳 Joriy balans: `{balance:,.2f}`"
      f" so'm\n💸 Jami xarajatlar: `{total_exp:,.2f}` so'm\n\n📂 *Kategoriyalar"
      " bo'yicha:*\n"
  )
  if cats:
    for cat_name, sum_val in cats:
      text += f"• {cat_name}: `{sum_val:,.2f}` so'm\n"
  else:
    text += "Hozircha xarajatlar yo'q."

  await message.answer(text, parse_mode="Markdown")


# --- /WEEKLY (Haftalik hisobot) ---
@router.message(Command("weekly"))
async def cmd_weekly(message: Message):
  user_id = message.from_user.id
  week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute(
      """
        SELECT SUM(amount) FROM expenses 
        WHERE user_id = ? AND date >= ?
    """,
      (user_id, week_ago),
  )
  total = cursor.fetchone()[0] or 0.0

  cursor.execute(
      """
        SELECT c.name, SUM(e.amount) 
        FROM expenses e 
        JOIN categories c ON e.category_id = c.id 
        WHERE e.user_id = ? AND e.date >= ?
        GROUP BY c.name
    """,
      (user_id, week_ago),
  )
  cats = cursor.fetchall()
  conn.close()

  text = f"📅 *Oxirgi 7 kunlik hisobot*\n\n💸 Jami xarajat: `{total:,.2f}` so'm\n\n"
  if cats:
    for cat_name, sum_val in cats:
      text += f"• {cat_name}: `{sum_val:,.2f}` so'm\n"
  else:
    text += "Bu hafta xarajatlar amalga oshirilmagan."

  await message.answer(text, parse_mode="Markdown")


# --- /MONTHLY (Oylik hisobot) ---
@router.message(Command("monthly"))
async def cmd_monthly(message: Message):
  user_id = message.from_user.id
  month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute(
      """
        SELECT SUM(amount) FROM expenses 
        WHERE user_id = ? AND date >= ?
    """,
      (user_id, month_ago),
  )
  total = cursor.fetchone()[0] or 0.0

  cursor.execute(
      """
        SELECT c.name, SUM(e.amount) 
        FROM expenses e 
        JOIN categories c ON e.category_id = c.id 
        WHERE e.user_id = ? AND e.date >= ?
        GROUP BY c.name
    """,
      (user_id, month_ago),
  )
  cats = cursor.fetchall()
  conn.close()

  text = f"📈 *Oxirgi 30 kunlik hisobot*\n\n💸 Jami xarajat: `{total:,.2f}` so'm\n\n"
  if cats:
    for cat_name, sum_val in cats:
      text += f"• {cat_name}: `{sum_val:,.2f}` so'm\n"
  else:
    text += "Bu oy xarajatlar amalga oshirilmagan."

  await message.answer(text, parse_mode="Markdown")


# --- /UNDO (Oxirgi xarajatni bekor qilish) ---
@router.message(Command("undo"))
async def cmd_undo(message: Message):
  user_id = message.from_user.id
  conn = get_connection()
  cursor = conn.cursor()

  cursor.execute(
      """
        SELECT id, amount, item_name FROM expenses 
        WHERE user_id = ? 
        ORDER BY id DESC LIMIT 1
    """,
      (user_id,),
  )
  last_exp = cursor.fetchone()

  if not last_exp:
    conn.close()
    await message.answer("❌ Bekor qilish uchun oxirgi xarajat topilmadi.")
    return

  exp_id, amount, item_name = last_exp

  cursor.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
  cursor.execute(
      "UPDATE users SET balance = balance + ? WHERE user_id = ?",
      (amount, user_id),
  )
  conn.commit()
  conn.close()

  await message.answer(
      "↩️ Oxirgi xarajat bekor qilindi va summa balansingizga qaytarildi:\n"
      f"💵 Summa: `{amount:,.2f}` so'm\n"
      f"📝 Izoh: {item_name}",
      parse_mode="Markdown",
  )


# --- /SETTINGS (Sozlamalar) ---
@router.message(Command("settings"))
async def cmd_settings(message: Message):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="🗑 Barcha ma'lumotlarni tozalash",
                  callback_data="clear_all_data",
              )
          ]
      ]
  )
  await message.answer(
      "⚙️ *Sozlamalar menyusi*:", reply_markup=keyboard, parse_mode="Markdown"
  )


@router.callback_query(F.data == "clear_all_data")
async def clear_data_callback(callback: CallbackQuery):
  user_id = callback.from_user.id
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
  cursor.execute(
      "UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,)
  )
  conn.commit()
  conn.close()
  await callback.message.edit_text(
      "🗑 Barcha xarajatlar va balansingiz tozalandi!"
  )
  await callback.answer()


# --- ASOSIY MAIN FUNKSIYASI ---
async def main():
  seed_categories()
  logging.info("Ma'lumotlar bazasi tekshirildi va tayyor.")

  dp.include_router(router)
  await bot.delete_webhook(drop_pending_updates=True)
  logging.info("Telegram bot ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  # 1. Flask serverni orqa fonda ishga tushiramiz (Render/Web service band bo'lib qolmasligi uchun)
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  # 2. Aiogram botni asosiy oqimda ishga tushiramiz
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    logging.info("Bot to'xtatildi.")
