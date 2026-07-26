import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from app.keyboards.reply import get_main_menu, get_settings_menu

# Router yaratamiz (Aiogram 3 da barcha handlerlar routerga ulanadi)
user_router = Router()

@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    """/start buyrug'i bosilganda ishlaydi"""
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    # Kelajakda bu yerda foydalanuvchini bazaga qo'shish funksiyasi ishlaydi
    logging.info(f"Yangi foydalanuvchi kirdi: {full_name} (ID: {user_id})")

    await message.answer(
        f"Salom, {full_name}! 👋\n\n"
        f"Men sizning shaxsiy moliyaviy yordamchingizman.\n"
        f"Xarajat kiritish uchun shunchaki matn yozing (Masalan: `Non 18000` yoki `Taxi 30000`).",
        reply_markup=get_main_menu()
    )

@user_router.message(F.text == "⚙️ Sozlamalar")
async def process_settings(message: types.Message):
    """Sozlamalar tugmasi bosilganda"""
    await message.answer("⚙️ Sozlamalar bo'limidasiz. Nima o'zgartiramiz?", reply_markup=get_settings_menu())

@user_router.message(F.text == "⬅️ Ortga")
async def process_back(message: types.Message):
    """Ortga qaytish tugmasi bosilganda"""
    await message.answer("Asosiy menyuga qaytdik 🏠", reply_markup=get_main_menu())
