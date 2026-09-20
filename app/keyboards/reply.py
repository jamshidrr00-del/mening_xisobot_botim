from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo

def get_main_menu():
    # Mini App (Web App) uchun maxsus tugma yaratamiz
    # URL manziliga sizning Render'dagi havolangiz qo'yildi
    web_app_btn = KeyboardButton(
        text="📱 Ilovani ochish (Mini App)", 
        web_app=WebAppInfo(url="https://mening-xisobot-botim.onrender.com")
    )
    
    # Asosiy menyu tugmalari
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [web_app_btn],  # Mini App tugmasi eng tepada, katta bo'lib turadi
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="➕ Xarajat")],
            [KeyboardButton(text="📆 Haftalik"), KeyboardButton(text="📅 Oylik")],
            [KeyboardButton(text="📂 Arxiv"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="🗑 Tozalash")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Quyidagilardan birini tanlang..." # Pastda chiroyli yozuv turadi
    )
    return keyboard

def get_settings_menu() -> ReplyKeyboardMarkup:
    """Sozlamalar menyusi tugmalarini yaratish"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿/🇷🇺 Til"), KeyboardButton(text="🗂 Kategoriyalar")],
            [KeyboardButton(text="📄 PDF eksport"), KeyboardButton(text="📊 Excel eksport")],
            [KeyboardButton(text="⏱ Vaqt zonasi"), KeyboardButton(text="⬅️ Ortga")]
        ],
        resize_keyboard=True
    )
    return keyboard
