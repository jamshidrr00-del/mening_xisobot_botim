import re

def get_category(item_name: str) -> str:
    """Kategoriyalarni avtomatik aniqlash funksiyasi"""
    name = item_name.lower()
    if any(word in name for word in ['non', 'gril', 'suv', 'tuxum', 'yog', 'shakar', 'choy']):
        return "🛒 Magazin"
    elif any(word in name for word in ['taxi', 'taksi', 'avtobus', 'metro', 'yol']):
        return "🚕 Transport"
    elif any(word in name for word in ['benzin', 'metan', 'prop', 'gaz', 'moy']):
        return "⛽️ Yoqilg'i"
    elif any(word in name for word in ['tok', 'svet', 'gaz puli', 'suv puli', 'musor']):
        return "💡 Komunal"
    return "🎁 Boshqa"

def parse_expense_text(text: str):
    text = text.strip()
    
    # 1-qolip: "Gril 4 ta 62000" (Nomi + soni + ta + donasi narxi)
    match1 = re.match(r'^(.*?)\s+(\d+)\s*ta\s+(\d+)$', text, re.IGNORECASE)
    
    # 2-qolip: "4 ta gril 62000" (Soni + ta + nomi + donasi narxi)
    match2 = re.match(r'^(\d+)\s*ta\s+(.*?)\s+(\d+)$', text, re.IGNORECASE)
    
    # 3-qolip: Oddiy xarajat "Non 18000" yoki "Taxi 30000"
    match3 = re.search(r'^(.*?)\s+(\d+)$', text, re.IGNORECASE)

    item_name = ""
    amount = 0

    if match1:
        name = match1.group(1).strip().capitalize()
        count = int(match1.group(2))
        price = int(match1.group(3))
        
        item_name = f"{name} {count} ta"
        amount = count * price  # Soni va narxini ko'paytiramiz
        
    elif match2:
        count = int(match2.group(1))
        name = match2.group(2).strip().capitalize()
        price = int(match2.group(3))
        
        item_name = f"{name} {count} ta"
        amount = count * price  # Soni va narxini ko'paytiramiz
        
    elif match3:
        item_name = match3.group(1).strip().capitalize()
        amount = int(match3.group(2))
    else:
        return None # Raqam topilmasa, xato qaytaradi (None)

    # Kategoriyani aniqlab olamiz
    category = get_category(item_name)

    return {
        "item_name": item_name,
        "amount": amount,
        "category": category
    }
