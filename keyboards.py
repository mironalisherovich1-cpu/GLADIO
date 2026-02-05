from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list"), InlineKeyboardButton(text="🔄 Обмен", callback_data="exchange")],
        [InlineKeyboardButton(text="💬 Отзывы", callback_data="reviews"), InlineKeyboardButton(text="❓ Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="📢 Канал", url="https://t.me/your_channel")]
    ])

def kb_cities():
    # Shaharlar ro'yxati
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Бухара", callback_data="city:bukhara")],
        [InlineKeyboardButton(text="📍 Ташкент", callback_data="city:tashkent")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
