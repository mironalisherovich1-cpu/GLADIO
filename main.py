import os
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import db
import keyboards as kb

# ----------------- SOZLAMALAR -----------------
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
BASE_URL = os.getenv("BASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# ✅ YANGILANGAN RASM (Ishlashi aniq bo'lgan havola)
IMAGE_URL = "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Admin uchun holatlar (States)
class AddProduct(StatesGroup):
    title = State()
    price = State()
    city = State()
    content = State()

# ----------------- LIFESPAN (ISHGA TUSHISH) -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bazani ulash
    await db.init_db()
    
    # Webhookni sozlash
    webhook_url = f"{BASE_URL}/tg_webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook o'rnatildi: {webhook_url}")
    
    yield
    
    # Bot o'chganda webhookni olib tashlash
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

# ----------------- FOYDALANUVCHI QISMI -----------------

@dp.message(CommandStart())
async def start(message: types.Message):
    await db.ensure_user(message.from_user.id, message.from_user.username)
    # Rasm bilan shahar tanlash menyusini chiqarish
    await message.answer_photo(
        photo=IMAGE_URL,
        caption="🏙 **Пожалуйста, выберите ваш город из списка:**",
        reply_markup=kb.kb_cities(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("city:"))
async def select_city(call: types.CallbackQuery):
    city_name = call.data.split(":")[1]
    # Shaharni bazaga saqlash
    await db.update_user_city(call.from_user.id, city_name)
    
    # Rasmni o'zgartirmasdan, faqat matnni yangilash
    await call.message.edit_caption(
        caption=f"✅ **Город выбран: {city_name.capitalize()}**\n\nДобро пожаловать в главное меню!",
        reply_markup=kb.kb_main(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    if not u:
        await call.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    text = (
        f"👤 **Твой id:** `[{u['user_id']}]`\n"
        f"🏙 **Твой город:** {u['city'].capitalize()}\n\n"
        f"🔥 **Скидка:** 0%\n"
        f"🏧 **Баланс:** {u['balance']} usd\n\n"
        f"◾️ Покупок: 0шт.\n"
        f"◾️ Находов: 0шт.\n"
        f"◾️ Ненаходов: 0шт."
    )
    # kb_back() funksiyasi keyboards.py da bo'lishi kerak
    # Agar yo'q bo'lsa, kb.kb_main() ishlatsa ham bo'ladi
    await call.message.edit_caption(caption=text, reply_markup=kb.kb_main(), parse_mode="Markdown")

@dp.callback_query(F.data == "shop_list")
async def show_shop(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    products = await db.get_products_by_city(u['city'])
    
    if not products:
        await call.answer(f"❌ В городе {u['city'].capitalize()} товаров пока нет", show_alert=True)
        return
        
    await call.message.edit_caption(
        caption=f"🛒 **Доступные товары ({u['city'].capitalize()}):**", 
        reply_markup=kb.kb_shop(products), 
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "back_to_start")
async def back_to_menu(call: types.CallbackQuery):
    await call.message.edit_caption(
        caption="🏠 **Главное меню:**", 
        reply_markup=kb.kb_main(), 
        parse_mode="Markdown"
    )

# ----------------- ADMIN PANEL -----------------

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_add")
async def add_pr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.answer("1. Введите название товара:")

@dp.message(AddProduct.title)
async def add_pr_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("2. Введите цену (USD, только число, например: 10.5):")

@dp.message(AddProduct.price)
async def add_pr_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProduct.city)
        await message.answer("3. Введите город (например: bukhara yoki tashkent):")
    except ValueError:
        await message.answer("❌ Ошибка! Введите цену числом (например: 5.0)")

@dp.message(AddProduct.city)
async def add_pr_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await state.set_state(AddProduct.content)
    await message.answer("4. Введите контент (ссылка или текст, который получит покупатель):")

@dp.message(AddProduct.content)
async def add_pr_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Bazaga qo'shish
    await db.add_product_to_db(data['title'], data['price'], message.text, data['city'])
    
    await state.clear()
    await message.answer(f"✅ Товар '{data['title']}' успешно добавлен в город {data['city']}!")

# ----------------- WEBHOOKLAR (Telegram & To'lov) -----------------

@app.post("/tg_webhook")
async def tg_webhook(request: Request):
    try:
        update = types.Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logging.error(f"Webhook update error: {e}")
    return {"ok": True}

@app.post("/nowpayments/ipn")
async def ipn_webhook(request: Request):
    # IPN logikasi keyinchalik to'liq qo'shiladi
    return {"ok": True}

# Agar lokal kompyuterda ishlatilsa
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
