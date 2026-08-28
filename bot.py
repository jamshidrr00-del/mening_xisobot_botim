import json
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Web App joylashgan HTTPS havola (GitHub Pages yoki Render manzilingiz)
WEB_APP_URL = "https://sizning-nikingiz.github.io/smart-expense-app/"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Web App darchasini ochadigan tugma
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="📱 Xarajat qo'shish (Mini App)", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    
    await update.message.reply_text(
        "Xush kelibsiz! Xarajatlarni kiritish uchun pastdagi tugmani bosing:",
        reply_markup=keyboard
    )

# Mini App'dan ma'lumot kelganda ishlovchi funksiya
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Web App yuborgan JSON ma'lumotni o'qiymiz
    data_str = update.effective_message.web_app_data.data
    data = json.loads(data_str)
    
    user_id = update.effective_user.id
    category = data['category']
    item_name = data['item_name']
    amount = data['amount']
    currency = data['currency']

    # Ma'lumotlar bazasiga saqlash (SQLite)
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses 
                      (user_id INTEGER, category TEXT, item_name TEXT, amount REAL, currency TEXT, date DATE DEFAULT CURRENT_DATE)''')
    
    cursor.execute("INSERT INTO expenses (user_id, category, item_name, amount, currency) VALUES (?, ?, ?, ?, ?)",
                   (user_id, category, item_name, amount, currency))
    conn.commit()
    conn.close()

    # Foydalanuvchiga tasdiq xabarini yuborish
    text = (f"✅ **Xarajat saqlandi!**\n\n"
            f"🏷 Kategoriya: {category}\n"
            f"📦 Mahsulot: {item_name}\n"
            f"💰 Summa: {amount:,.0f} {currency}")
    
    await update.message.reply_text(text, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token("BOT_TOKENINGIZNI_YAZING").build()

    app.add_handler(CommandHandler("start", start))
    # Web App ma'lumotlarini ushlab oluvchi filter
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

    app.run_polling()
