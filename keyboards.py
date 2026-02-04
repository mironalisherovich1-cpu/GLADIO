from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ])

def kb_shop(products):
    # products — bu bazadan kelgan mahsulotlar ro'yxati
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(text=f"{p['title']} — {p['price_usd']}$", callback_data=f"buy:{p['id']}:{p['price_usd']}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
    ])
