import re

def get_category(item_name: str) -> str:
    """Kategoriyalarni avtomatik aniqlash funksiyasi"""
    name = item_name.lower()
    # Magazin ro'yxatiga guruch, makaron kabilarni ham qo'shdik
    if any(word in name for word in ['non', 'gril', 'suv', 'tuxum', 'yog', 'shakar', 'choy', 'guruch', 'makaron']):
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
            
        # Qoliplarni tekshirish (ta, kg, l, litr va kasr sonlar masalan 1.5 kg qo'shildi)
        match1 = re.match(r'^(.*?)\s+(\d+(?:\.\d+)?)\s*(ta|kg|l|litr)\s+(\d+)$', line, re.IGNORECASE)
        match2 = re.match(r'^(\d+(?:\.\d+)?)\s*(ta|kg|l|litr)\s+(.*?)\s+(\d+)$', line, re.IGNORECASE)
        match3 = re.search(r'^(.*?)\s+(\d+)$', line, re.IGNORECASE)

        item_name = ""
        amount = 0

        if match1:
            name = match1.group(1).strip().capitalize()
            count = float(match1.group(2))
            unit = match1.group(3).lower()
            price = int(match1.group(4))
            
            # Kasr son bo'lmasa butun songa aylantiramiz (masalan 2.0 emas 2 bo'lishi uchun)
            count_display = int(count) if count.is_integer() else count
            
            item_name = f"{name} {count_display} {unit}"
            amount = int(count * price)
            
        elif match2:
            count = float(match2.group(1))
            unit = match2.group(2).lower()
            name = match2.group(3).strip().capitalize()
            price = int(match2.group(4))
            
            count_display = int(count) if count.is_integer() else count
            
            item_name = f"{name} {count_display} {unit}"
            amount = int(count * price)
            
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

    return results
