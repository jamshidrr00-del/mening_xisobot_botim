import telebot
import json
import os
from datetime import date
from flask import Flask
from threading import Thread

# --- RENDER UCHUN MITTI VEB-SAYT (PORT OCHISH) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot onlayn va ishlayapti!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Veb serverni alohida fonda ishga tushirish
t = Thread(target=run_web)
t.start()
# ------------------------------------------------

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@bot.message_handler(commands=['start'])
def start(message):
    text = (
        "📊 Kunlik hisob botiga xush kelibsiz!\n\n"
        "Yozish formati:\n"
        "JOY SUMMA\n\n"
        "Misol:\n"
        "Bozor 15000\n\n"
        "Buyruqlar:\n"
        "/hisobot — bugungi hisob\n"
        "/tozalash — kunni yopish"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['hisobot'])
def report(message):
    data = load_data()
    today = str(date.today())

    if today not in data or not data[today]:
        bot.reply_to(message, "Bugun hali ma’lumot yo‘q ❌")
        return

    text = "📅 Bugungi hisobot:\n\n"
    jami = 0

    for joy, summa in data[today].items():
        text += f"{joy} — {sum(summa)} so‘m\n"
        jami += sum(summa)

    text += f"\n————————\nJAMI: {jami} so‘m"
    bot.reply_to(message, text)

@bot.message_handler(commands=['tozalash'])
def clear(message):
    data = load_data()
    today = str(date.today())

    if today in data:
        del data[today]
        save_data(data)
        bot.reply_to(message, "✅ Bugungi hisob yopildi, ma’lumotlar tozalandi")
    else:
        bot.reply_to(message, "Bugun uchun ma’lumot yo‘q")

@bot.message_handler(func=lambda m: True)
def add_expense(message):
    try:
        joy, summa = message.text.rsplit(" ", 1)
        summa = int(summa)
    except Exception:
        bot.reply_to(message, "❌ Format xato\nMisol: Bozor 15000")
        return

    data = load_data()
    today = str(date.today())

    if today not in data:
        data[today] = {}

    if joy not in data[today]:
        data[today][joy] = []

    data[today][joy].append(summa)
    save_data(data)

    bot.reply_to(
        message,
        f"✅ Saqlandi:\n{joy} +{summa} so‘m"
    )

print("Bot ishga tushdi...")
bot.infinity_polling()
