import re

# TZ bo'yicha avtomatik kategoriya topish uchun lug'at
CATEGORY_MAPPING = {
    "🛒 Magazin": ["non", "sut", "qatiq", "tuxum", "suv", "olma", "kartoshka", "piyoz", "go'sht", "choy", "shakar", "makaron"],
    "🚕 Transport": ["taxi", "taksi", "avtobus", "metro", "yo'l", "yol"],
    "💊 Apteka": ["dori", "paratsetamol", "analgin", "maz", "apteka", "bint", "shprits", "vitamin"],
    "⛽️ Yoqilg'i": ["ai80", "ai91", "ai92", "benzin", "gaz", "metan", "propan", "zapravka"],
    "🍔 Kafe": ["kafe", "osh", "somsa", "kofe", "burger", "lavash", "hotdog", "shashlik", "choyxona"],
    "💡 Kommunal": ["svet", "tok", "suv", "gaz", "musor", "kvitansiya"],
    "🌐 Internet": ["internet", "wifi", "uzmobile", "beeline", "ucell", "mobiuz", "paynet"]
}

def determine_category(item_name: str) -> str:
    """Xarajat nomiga qarab uning kategoriyasini avtomatik aniqlash"""
    name_lower = item_name.lower()
    
    for category, keywords in CATEGORY_MAPPING.items():
        for keyword in keywords:
            # Agar mahsulot nomi ichida kalit so'z bo'lsa (masalan "2 ta non" ichida "non" bor)
            if keyword in name_lower:
                return category
                
    return "🎁 Boshqa" # Hech qaysiga tushmasa

def parse_expense_text(text: str):
    """Foydalanuvchi matnidan nom, miqdor va summani ajratib olish"""
    # Matn ichidan barcha raqamlarni topamiz (masalan, "2 ta non 36000" -> ['2', '36000'])
    numbers = re.findall(r'\d+', text)
    
    if not numbers:
        return None # Raqam topilmadi
        
    # Qoidaga ko'ra, eng oxirgi yozilgan raqam doim JAMI SUMMA hisoblanadi
    amount = int(numbers[-1])
    
    # Summani olib tashlab, qolganini mahsulot nomi deb olamiz
    item_name = text.replace(str(amount), "", 1).strip()
    
    # Ortiqcha belgilarni (-, =, :, bo'sh joy) tozalaymiz
    item_name = re.sub(r'^[ \t\r\n\-\:\=\+]+|[ \t\r\n\-\:\=\+]+$', '', item_name).strip()
    
    if not item_name:
        item_name = "Xarajat"
        
    # Kategoriyani avtomatik aniqlaymiz
    category = determine_category(item_name)
    
    return {
        "item_name": item_name,
        "amount": amount,
        "category": category
    }
