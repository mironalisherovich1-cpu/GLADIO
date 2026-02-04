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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddProduct(StatesGroup):
    title = State()
    price = State()
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
    await message.answer(f"👋 Привет, {message.from_user.full_name}!", reply_markup=kb.kb_main())

@dp.callback_query(F.data == "shop_list")
async def shop(call: types.CallbackQuery):
    products = await db.get_all_products()
    if not products:
        await call.answer("📦 Товаров пока нет.", show_alert=True)
        return
    await call.message.edit_text("Выберите товар:", reply_markup=kb.kb_shop(products))

@dp.callback_query(F.data == "back_to_start")
async def back(call: types.CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=kb.kb_main())

@dp.callback_query(F.data.startswith("buy:"))
async def buy(call: types.CallbackQuery):
    _, p_id, price = call.data.split(":")
    async with httpx.AsyncClient() as client:
        payload = {"price_amount": float(price), "price_currency": "usd", "pay_currency": "ltc", "order_id": f"U{call.from_user.id}P{p_id}"}
        headers = {"x-api-key": NP_API_KEY}
        resp = await client.post("https://api.nowpayments.io/v1/payment", json=payload, headers=headers)
        data = resp.json()

    if "payment_id" in data:
        await db.create_order(data['payment_id'], call.from_user.id, int(p_id), data['pay_amount'])
        await call.message.answer(f"⚠️ Оплата LTC\nСумма: `{data['pay_amount']}`\nАдрес: `{data['pay_address']}`", parse_mode="Markdown")
    else:
        await call.answer("Ошибка платежа.")

# --- ADMIN HANDLERS ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin(message: types.Message):
    await message.answer("Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_add", F.from_user.id == ADMIN_ID)
async def add_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.answer("Название товара:")

@dp.message(AddProduct.title)
async def add_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("Цена (USD):")

@dp.message(AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    await state.update_data(price=float(message.text))
    await state.set_state(AddProduct.content)
    await message.answer("Контент (ссылка/код):")

@dp.message(AddProduct.content)
async def add_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product_to_db(data['title'], data['price'], message.text)
    await state.clear()
    await message.answer("✅ Добавлено!")

# --- WEBHOOKS ---
@app.post("/tg_webhook")
async def tg_wh(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)

@app.post("/nowpayments/ipn")
async def np_wh(request: Request):
    data = await request.json()
    if data.get("payment_status") in ["confirmed", "finished"]:
        order = await db.get_order_by_payment(str(data.get("payment_id")))
        if order and order['status'] == 'waiting':
            await db.set_order_status(order['payment_id'], "paid")
            prod = await db.get_product(order['product_id'])
            await bot.send_message(order['user_id'], f"✅ Оплачено! Ваш товар:\n{prod['content']}")
    return {"ok": True}
