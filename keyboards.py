from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Asosiy menyu (Bu yerga orqaga tugmasi kerak emas)
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list"), InlineKeyboardButton(text="🔄 Обмен", callback_data="exchange")],
        [InlineKeyboardButton(text="💬 Отзывы", callback_data="reviews"), InlineKeyboardButton(text="❓ Поддержка", callback_data="support")],
        # Kanalingiz linkini shu yerga yozing
        [InlineKeyboardButton(text="📢 Канал", url="https://t.me/sizning_kanalingiz")]
    ])

# Shahar tanlash (Orqaga tugmasi qo'shildi)
def kb_cities():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Бухара", callback_data="city:bukhara")],
        [InlineKeyboardButton(text="📍 Ташкент", callback_data="city:tashkent")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# Profil menyusi (Orqaga tugmasi bor)
def kb_profile():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"), InlineKeyboardButton(text="🎁 Промокод", callback_data="promo")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# Do'kon menyusi (Har bir tovar tagida va oxirida orqaga tugmasi bo'ladi)
def kb_shop(products):
    buttons = []
    for p in products:
        # Tovar nomi va narxi
        btn_text = f"{p['title']} - {p['price_usd']}$"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy:{p['id']}")])
    
    # Ro'yxat oxiriga "Orqaga" tugmasi
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Admin paneli (Orqaga tugmasi bor)
def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="⬅️ Выйти в меню", callback_data="back_to_start")]
    ])

# Universal "Orqaga" tugmasi (Matnli xabarlar uchun)
def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])
