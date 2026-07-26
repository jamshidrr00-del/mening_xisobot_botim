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
    # Vergullarni ham yangi qatorga aylantirib olamiz (qulaylik uchun)
    text = text.replace(',', '\n')
    lines = text.strip().split('\n')
    
    results = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Qoliplarni tekshirish
        match1 = re.match(r'^(.*?)\s+(\d+)\s*ta\s+(\d+)$', line, re.IGNORECASE)
        match2 = re.match(r'^(\d+)\s*ta\s+(.*?)\s+(\d+)$', line, re.IGNORECASE)
        match3 = re.search(r'^(.*?)\s+(\d+)$', line, re.IGNORECASE)

        item_name = ""
        amount = 0

        if match1:
            name = match1.group(1).strip().capitalize()
            count = int(match1.group(2))
            price = int(match1.group(3))
            item_name = f"{name} {count} ta"
            amount = count * price
        elif match2:
            count = int(match2.group(1))
            name = match2.group(2).strip().capitalize()
            price = int(match2.group(3))
            item_name = f"{name} {count} ta"
            amount = count * price
        elif match3:
            item_name = match3.group(1).strip().capitalize()
            amount = int(match3.group(2))
        else:
            continue # Tushunarsiz qatorlarni o'tkazib yuboradi

        category = get_category(item_name)
        results.append({
            "item_name": item_name,
            "amount": amount,
            "category": category
        })

    return results # Endi bitta xarajat emas, ro'yxat (spiska) qaytaradi
