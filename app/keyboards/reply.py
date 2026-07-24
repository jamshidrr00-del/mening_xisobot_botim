from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="➕ Xarajat")],
            [KeyboardButton(text="📆 Haftalik"), KeyboardButton(text="📅 Oylik")],
            [KeyboardButton(text="📂 Arxiv"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="🗑 Tozalash")]
        ],
        resize_keyboard=True
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
