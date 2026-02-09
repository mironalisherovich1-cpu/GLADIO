from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- ASOSIY REPLY MENU (PASTDA) ---
def kb_reply_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Главное меню")]], resize_keyboard=True, persistent=True)

# --- ASOSIY MENU (INLINE) ---
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list")],
        # Podderjka o'zgartirildi: chapo73
        # Otzivlar kanali: Siz bergan ssilka
        [InlineKeyboardButton(text="🔄 Обмен LTC", url="https://t.me/ltc_obmen"), InlineKeyboardButton(text="❓ Поддержка", url="https://t.me/chapo73")],
        [InlineKeyboardButton(text="💬 Отзывы (Канал)", url="https://t.me/+a2w0f5tt22UyN2Qy")]
    ])

# --- SHAHAR TANLASH ---
def kb_cities():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Бухара", callback_data="city:bukhara")],
        [InlineKeyboardButton(text="📍 Ташкент", callback_data="city:tashkent")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# --- PROFIL MENYUSI ---
def kb_profile():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit_balance")],
        [InlineKeyboardButton(text="📜 История покупок", callback_data="history"), InlineKeyboardButton(text="👥 Рефералка", callback_data="referral")],
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

# --- MAGAZIN (TOVARLAR RO'YXATI) ---
def kb_shop(grouped_products):
    buttons = []
    for p in grouped_products:
        # Userga soni ko'rinmaydi, faqat nomi va narxi
        btn_text = f"{p['title']} - {p['price_usd']}$"
        callback = f"buy_title:{p['title']}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ADMIN PANEL ---
def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data="admin_delete")],
        [InlineKeyboardButton(text="📦 Склад (Остаток)", callback_data="admin_stock")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Баланс юзера", callback_data="admin_balance")],
        [InlineKeyboardButton(text="🖼 Изменить фото", callback_data="admin_photo")],
        [InlineKeyboardButton(text="⬅️ Выйти", callback_data="back_to_start")]
    ])

# --- ADMIN O'CHIRISH RO'YXATI ---
def kb_admin_delete_list(grouped_products):
    buttons = []
    for p in grouped_products:
        # Admin nechta borligini ko'rib turadi
        btn_text = f"❌ {p['title']} (Всего: {p['count']} шт)"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"del_grp:{p['title']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- QAYTISH TUGMASI ---
def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]])

# --- OTZIV QOLDIRISH TUGMASI (TOVAR OLGACH) ---
def kb_leave_review():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="write_review")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])
