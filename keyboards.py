from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# 1. DOIMIY TUGMA (Pastda turadigan)
def kb_reply_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True, # Tugma kichkina va chiroyli bo'ladi
        persistent=True       # Har doim ko'rinib turadi
    )

# 2. ASOSIY MENYU (Linklar o'zgardi)
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list")],
        # Linklar to'g'ridan-to'g'ri odamlarga o'tadi
        [InlineKeyboardButton(text="🔄 Обмен LTC", url="https://t.me/ltc_obmen"), InlineKeyboardButton(text="❓ Поддержка", url="https://t.me/chapo83")],
        # Otzivi kanali (o'zingizning otziv kanalingizni qo'yishingiz mumkin)
        [InlineKeyboardButton(text="💬 Отзывы", url="https://t.me/sizning_otzivi_kanalingiz")]
    ])

def kb_cities():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Бухара", callback_data="city:bukhara")],
        [InlineKeyboardButton(text="📍 Ташкент", callback_data="city:tashkent")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

def kb_profile():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"), InlineKeyboardButton(text="🎁 Промокод", callback_data="promo")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

def kb_shop(products):
    buttons = []
    for p in products:
        btn_text = f"{p['title']} - {p['price_usd']}$"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy:{p['id']}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Admin paneli
def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="⬅️ Выйти в меню", callback_data="back_to_start")]
    ])

# Orqaga tugmasi
def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# 3. SOTIB OLGANDAN KEYIN SHARH QOLDIRISH TUGMASI
def kb_leave_review():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="write_review")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])
