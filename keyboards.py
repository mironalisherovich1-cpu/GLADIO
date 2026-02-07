from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Asosiy menyu (Pastdagi)
def kb_reply_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Главное меню")]], resize_keyboard=True, persistent=True)

# Asosiy menyu (Tepadagi rasm ostida)
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list")],
        [InlineKeyboardButton(text="🔄 Обмен LTC", url="https://t.me/ltc_obmen"), InlineKeyboardButton(text="❓ Поддержка", url="https://t.me/chapo83")],
        [InlineKeyboardButton(text="💬 Отзывы", url="https://t.me/sizning_otzivi_kanalingiz")]
    ])

# Shaharlar
def kb_cities():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Бухара", callback_data="city:bukhara")],
        [InlineKeyboardButton(text="📍 Ташкент", callback_data="city:tashkent")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# Profil menyusi (YANGILANGAN)
def kb_profile():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit_balance")],
        [InlineKeyboardButton(text="📜 История покупок", callback_data="history"), InlineKeyboardButton(text="👥 Рефералка", callback_data="referral")],
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# Magazin (User uchun - Soni ko'rinmaydi)
def kb_shop(grouped_products):
    buttons = []
    for p in grouped_products:
        # Faqat Nomi va Narxi
        btn_text = f"{p['title']} - {p['price_usd']}$"
        callback = f"buy_title:{p['title']}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Admin menyusi (YANGILANGAN)
def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data="admin_delete")],
        [InlineKeyboardButton(text="📦 Склад (Остаток)", callback_data="admin_stock")], # YANGI
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")], # YANGI
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Баланс юзера", callback_data="admin_balance")],
        [InlineKeyboardButton(text="🖼 Изменить фото", callback_data="admin_photo")],
        [InlineKeyboardButton(text="⬅️ Выйти", callback_data="back_to_start")]
    ])

# Admin o'chirish ro'yxati (Bu yerda soni ko'rinadi)
def kb_admin_delete_list(grouped_products):
    buttons = []
    for p in grouped_products:
        btn_text = f"❌ {p['title']} (Jami: {p['count']} ta)"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"del_grp:{p['title']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]])

def kb_leave_review():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="write_review")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])
