import re
import sqlite3
from datetime import datetime
import pytz
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# O'zingizning bazangiz fayllari
from app.database.db import DB_PATH, add_user, update_balance, get_balance

user_router = Router()

class FSM(StatesGroup):
    income = State()

# ================= KIRIM (DAROMAD) QISMI =================

@user_router.message(Command("kirim"))
async def cmd_kirim(message: types.Message, state: FSMContext):
    await message.answer("💰 Balansga qo'shmoqchi bo'lgan summani kiriting (masalan: 1500000 yoki 15 000 000):")
    await state.set_state(FSM.income)

@user_router.message(F.state == FSM.income, F.text)
async def process_income(message: types.Message, state: FSMContext):
    # Probellarni olib tashlab tekshirish
    text = message.text.replace(" ", "")
    
    if text.isdigit():
        amount = int(text)
        user_id = message.from_user.id
        add_user(user_id) # Bazada yo'q bo'lsa qo'shish
        
        # Bazaga pulni qo'shish
        update_balance(user_id, amount)
        current_balance = get_balance(user_id)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Oxirgi kirimni o'chirish", callback_data=f"undo_inc_{amount}")]
        ])
        
        await message.answer(
            f"✅ Balansga {amount:,.0f} so'm qo'shildi.\n💳 Joriy balans: {current_balance:,.0f} so'm", 
            reply_markup=kb
        )
        await state.clear()
    else:
        await message.answer("❌ Noto'g'ri summa kiritildi. Iltimos, faqat raqam kiriting:")

@user_router.callback_query(F.data.startswith("undo_inc_"))
async def undo_income(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Bazadan pulni ayirish (bekor qilish)
    update_balance(user_id, -amount)
    current_balance = get_balance(user_id)
    
    await callback.message.edit_text(
        f"🗑 {amount:,.0f} so'm kirim bekor qilindi.\n💳 Joriy balans: {current_balance:,.0f} so'm"
    )
    await callback.answer("Kirim o'chirildi")

# ================= XARAJAT QISMI (BUYRUQLARSIZ) =================

@user_router.message(F.text)
async def process_expense(message: types.Message):
    if message.text.startswith('/'):
        return
        
    user_id = message.from_user.id
    add_user(user_id)
    lines = message.text.strip().split('\n')
    
    # Matnni qidiruvchi formula: (Nomi) (Soni) (O'lchovi) (Narxi)
    pattern = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr|m|metr)\s+([\d\s]+)$", re.IGNORECASE)
    
    response_lines = []
    total_expense = 0
    
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            name = match.group(1).strip().capitalize()
            qty_str = match.group(2)
            qty = float(qty_str) if '.' in qty_str else int(qty_str)
            unit = match.group(3).strip().lower()
            
            # Narxdagi probellarni tozalash
            price = int(match.group(4).replace(" ", ""))
            
            # Ko'paytirib hisoblash
            line_total = qty * price
            total_expense += line_total
            
            response_lines.append(f"✅ {name} {qty} {unit} {int(line_total)} so'm")
    
    if response_lines:
        # Bazadan jami xarajatni ayirish
        update_balance(user_id, -total_expense)
        current_balance = get_balance(user_id)
        
        final_text = "\n".join(response_lines)
        final_text += f"\n\n💳 Joriy balans: {current_balance:,.0f} so'm"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Xarajatni bekor qilish", callback_data=f"undo_exp_{total_expense}")]
        ])
        
        await message.answer(final_text, reply_markup=kb)
    else:
        await message.answer("⚠️ Iltimos, xarajatni quyidagi formatda kiriting:\n\nnon 4 ta 3000\nshakar 2 kg 10000")

@user_router.callback_query(F.data.startswith("undo_exp_"))
async def undo_expense(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Bekor qilinganda pulni bazaga qaytarish
    update_balance(user_id, amount)
    current_balance = get_balance(user_id)
    
    await callback.message.edit_text(
        f"🗑 Xarajat bekor qilindi va {amount:,.0f} so'm balansga qaytarildi.\n💳 Joriy balans: {current_balance:,.0f} so'm"
    )
    await callback.answer("Xarajat bekor qilindi")
