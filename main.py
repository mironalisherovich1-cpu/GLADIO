import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Header
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import httpx
from db import init_db, ensure_user, create_order, get_order_by_payment, set_order_status, get_product

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Переменные окружения (Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NP_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")
BASE_URL = os.getenv("BASE_URL") 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ----------------- LIFESPAN -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    webhook_url = f"{BASE_URL}/tg_webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook установлен: {webhook_url}")
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

# ----------------- HANDLERS -----------------
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await ensure_user(message.from_user.id, message.from_user.username)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_list")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ])
    await message.answer(
        f"👋 Привет, {message.from_user.full_name}!\n\n"
        f"Добро пожаловать в наш автоматизированный магазин. Выберите раздел:", 
        reply_markup=kb
    )

@dp.callback_query(F.data == "shop_list")
async def show_products(call: types.CallbackQuery):
    # В идеале товары должны тянуться из базы: await list_products()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 VIP Товар (10$)", callback_data="buy:1:10")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
    ])
    await call.message.edit_text("Выбирайте подходящий товар:", reply_markup=kb)

@dp.callback_query(F.data == "back_to_start")
async def back_start(call: types.CallbackQuery):
    await start_cmd(call.message)

@dp.callback_query(F.data.startswith("buy:"))
async def process_buy(call: types.CallbackQuery):
    _, p_id, price = call.data.split(":")
    
    # Создание платежа в NOWPayments
    async with httpx.AsyncClient() as client:
        payload = {
            "price_amount": float(price),
            "price_currency": "usd",
            "pay_currency": "ltc",
            "order_id": f"UID_{call.from_user.id}_PID_{p_id}",
            "order_description": f"Оплата товара #{p_id}"
        }
        headers = {"x-api-key": NP_API_KEY}
        resp = await client.post("https://api.nowpayments.io/v1/payment", json=payload, headers=headers)
        data = resp.json()

    if "payment_id" in data:
        payment_id = data['payment_id']
        pay_addr = data['pay_address']
        pay_amt = data['pay_amount']
        
        await create_order(payment_id, call.from_user.id, int(p_id), pay_amt)
        
        text = (
            f"⚠️ **Ожидание оплаты**\n\n"
            f"Отправьте ровно: `{pay_amt} LTC`\n"
            f"На адрес: `{pay_addr}`\n\n"
            f"💡 После подтверждения транзакции бот автоматически отправит вам товар."
        )
        await call.message.answer(text, parse_mode="Markdown")
    else:
        await call.answer("Ошибка при создании счета. Попробуйте позже.")

# ----------------- WEBHOOKS -----------------
@app.post("/tg_webhook")
async def telegram_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.post("/nowpayments/ipn")
async def np_webhook(request: Request):
    payload = await request.json()
    status = payload.get("payment_status")
    payment_id = str(payload.get("payment_id"))

    if status in ["confirmed", "finished"]:
        order = await get_order_by_payment(payment_id)
        if order and order['status'] != 'paid':
            await set_order_status(payment_id, "paid")
            
            # Получаем контент товара из базы
            product = await get_product(order['product_id'])
            content = product['content'] if product else "Ошибка получения товара. Свяжитесь с админом."
            
            await bot.send_message(
                order['user_id'], 
                f"✅ **Оплата получена!**\n\nВаш товар:\n`{content}`",
                parse_mode="Markdown"
            )
            
    return {"ok": True}
