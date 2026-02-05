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

# Настройки
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
BASE_URL = os.getenv("BASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Skrinshotdagi rasm uchun (o'zingiznikiga almashtirishingiz mumkin)
IMAGE_URL = "https://i.postimg.cc/qM3XzZ6D/main-png.png" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddProduct(StatesGroup):
    title = State()
    price = State()
    city = State()
    content = State()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await bot.set_webhook(f"{BASE_URL}/tg_webhook")
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

# --- USER HANDLERS ---
@dp.message(CommandStart())
async def start(message: types.Message):
    await db.ensure_user(message.from_user.id, message.from_user.username)
    await message.answer_photo(
        photo=IMAGE_URL,
        caption="🏙 **Пожалуйста, выберите ваш город из списка:**",
        reply_markup=kb.kb_cities(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("city:"))
async def select_city(call: types.CallbackQuery):
    city_name = call.data.split(":")[1]
    await db.update_user_city(call.from_user.id, city_name)
    await call.message.edit_caption(
        caption=f"✅ **Город выбран: {city_name.capitalize()}**\n\nДобро пожаловать в главное меню!",
        reply_markup=kb.kb_main(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    text = (
        f"👤 **Твой id:** `[{u['user_id']}]`\n"
        f"🏙 **Твой город:** {u['city'].capitalize()}\n\n"
        f"🔥 **Скидка:** 0%\n"
        f"🏧 **Баланс:** {u['balance']} usd\n\n"
        f"◾️ Покупок: 0шт.\n"
        f"◾️ Находов: 0шт.\n"
        f"◾️ Ненаходов: 0шт."
    )
    await call.message.edit_caption(caption=text, reply_markup=kb.kb_back(), parse_mode="Markdown")

@dp.callback_query(F.data == "shop_list")
async def show_shop(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    products = await db.get_products_by_city(u['city'])
    if not products:
        await call.answer("❌ В этом городе товаров пока нет", show_alert=True)
        return
    await call.message.edit_caption(caption="🛒 **Доступные товары:**", reply_markup=kb.kb_shop(products), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_start")
async def back_to_menu(call: types.CallbackQuery):
    await call.message.edit_caption(caption="🏠 **Главное меню:**", reply_markup=kb.kb_main(), parse_mode="Markdown")

# --- ADMIN HANDLERS (Soddalashtirilgan) ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_add")
async def add_pr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.answer("Введите название товара:")

@dp.message(AddProduct.title)
async def add_pr_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("Введите цену (USD):")

@dp.message(AddProduct.price)
async def add_pr_price(message: types.Message, state: FSMContext):
    await state.update_data(price=float(message.text))
    await state.set_state(AddProduct.city)
    await message.answer("Введите город (например: bukhara):")

@dp.message(AddProduct.city)
async def add_pr_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await state.set_state(AddProduct.content)
    await message.answer("Введите контент (ссылка/текст):")

@dp.message(AddProduct.content)
async def add_pr_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product_to_db(data['title'], data['price'], message.text, data['city'])
    await state.clear()
    await message.answer("✅ Товар успешно добавлен!")

# --- FASTAPI WEBHOOKS (Oldingi bilan bir xil) ---
@app.post("/tg_webhook")
async def tg_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)

@app.post("/nowpayments/ipn")
async def ipn_webhook(request: Request):
    # Oldingi IPN logikasi
    return {"ok": True}
