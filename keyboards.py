from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def kb_reply_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
        resize_keyboard=True, persistent=True
    )

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list")],
        [InlineKeyboardButton(text="🔄 Обмен LTC", url="https://t.me/ltc_obmen"), InlineKeyboardButton(text="❓ Поддержка", url="https://t.me/chapo83")],
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
        # Balans to'ldirish va Promokod
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit_balance")],
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

def kb_shop(products):
    buttons = []
    for p in products:
        btn_text = f"{p['title']} - {p['price_usd']}$"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy:{p['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# 🔥 KUCHAYTIRILGAN ADMIN PANEL
def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Изменить баланс юзера", callback_data="admin_balance")],
        [InlineKeyboardButton(text="🖼 Изменить фото меню", callback_data="admin_photo")],
        [InlineKeyboardButton(text="⬅️ Выйти", callback_data="back_to_start")]
    ])

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])

def kb_leave_review():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="write_review")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
    ])
