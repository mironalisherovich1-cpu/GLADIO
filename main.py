import os
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import db
import keyboards as kb

# ----------------- SOZLAMALAR -----------------
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
BASE_URL = os.getenv("BASE_URL") # https://... bilan bo'lishi shart
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Do'kon rasmi
IMAGE_URL = "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Admin uchun holatlar
class AddProduct(StatesGroup):
    title = State()
    price = State()
    city = State()
    content = State()

# ----------------- LIFESPAN & TO'LOV FUNKSIYALARI -----------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    webhook_url = f"{BASE_URL}/tg_webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook o'rnatildi: {webhook_url}")
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

async def create_nowpayments_invoice(price_usd):
    """
    NOWPayments da invoice yaratish va avtomatik LTC hisoblash
    """
    url = "https://api.nowpayments.io/v1/payment"
    headers = {
        "x-api-key": NP_API_KEY,
        "Content-Type": "application/json"
    }
    # Webhook manzili (IPN) shu yerda ko'rsatiladi
    data = {
        "price_amount": price_usd,
        "price_currency": "usd",
        "pay_currency": "ltc",
        "ipn_callback_url": f"{BASE_URL}/nowpayments/ipn" 
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 201:
                return response.json()
            else:
                logging.error(f"NP Error: {response.text}")
                return None
        except Exception as e:
            logging.error(f"Connection Error: {e}")
            return None

# ----------------- USER HANDLERS -----------------

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

@dp.callback_query(F.data.startswith("buy:"))
async def buy_start(call: types.CallbackQuery):
    product_id = call.data.split(":")[1]
    product = await db.get_product(product_id)
    
    if not product:
        await call.answer("❌ Товар не найден!", show_alert=True)
        return

    await call.message.edit_caption(caption="🔄 **Генерирую адрес для оплаты...**\nПожалуйста, подождите 2-3 секунды.", reply_markup=None, parse_mode="Markdown")

    # 1. Invoice yaratish
    payment_data = await create_nowpayments_invoice(product['price_usd'])
    
    if not payment_data:
        await call.message.answer("❌ Ошибка платежной системы. Попробуйте позже.")
        return

    pay_address = payment_data['pay_address']
    pay_amount = payment_data['pay_amount']
    payment_id = payment_data['payment_id']

    # 2. Bazaga "waiting" statusida saqlash
    await db.create_order(call.from_user.id, product_id, payment_id, pay_amount)

    # 3. Foydalanuvchiga ko'rsatish
    text = (
        f"🛒 **Покупка:** {product['title']}\n"
        f"💵 **Стоимость:** {product['price_usd']} USD\n"
        f"🔄 **К оплате:** `{pay_amount}` LTC\n\n"
        f"👇 **Отправьте точную сумму на этот адрес:**\n"
        f"`{pay_address}`\n\n"
        f"⏳ **Как только оплата пройдет (1-5 мин), бот АВТОМАТИЧЕСКИ пришлет вам товар.**\n"
        f"Ничего нажимать не нужно."
    )
    
    # Manzilni alohida xabar qilib tashlash (kopirovat qilish oson bo'lishi uchun)
    await call.message.answer(pay_address)
    # Chekni chiqarish (back tugmasi bilan)
    await call.message.answer(text, reply_markup=kb.kb_back(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_start")
async def back_to_menu(call: types.CallbackQuery):
    # Rasm o'chib ketmasligi uchun try-except ishlatamiz yoki yangi rasm yuboramiz
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer_photo(
        photo=IMAGE_URL,
        caption="🏠 **Главное меню:**",
        reply_markup=kb.kb_main(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    text = (
        f"👤 **Твой id:** `{u['user_id']}`\n"
        f"🏙 **Твой город:** {u['city'].capitalize()}\n"
        f"🏧 **Баланс:** {u['balance']} usd\n"
    )
    await call.message.edit_caption(caption=text, reply_markup=kb.kb_profile(), parse_mode="Markdown")

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
    await message.answer("2. Введите цену (USD, числом):")

@dp.message(AddProduct.price)
async def add_pr_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProduct.city)
        await message.answer("3. Введите город (например: bukhara):")
    except ValueError:
        await message.answer("❌ Ошибка! Цена должна быть числом (например: 10.5)")

@dp.message(AddProduct.city)
async def add_pr_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await state.set_state(AddProduct.content)
    await message.answer("4. Введите контент (ссылка или текст товара):")

@dp.message(AddProduct.content)
async def add_pr_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product_to_db(data['title'], data['price'], message.text, data['city'])
    await state.clear()
    await message.answer("✅ Товар успешно добавлен!")

# ----------------- WEBHOOKS -----------------

@app.post("/tg_webhook")
async def tg_webhook(request: Request):
    try:
        update = types.Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logging.error(f"Telegram Webhook Error: {e}")
    return {"ok": True}

# 🔥 AVTOMATIK TO'LOV QABUL QILISH (IPN)
@app.post("/nowpayments/ipn")
async def ipn_webhook(request: Request):
    try:
        data = await request.json()
        logging.info(f"Yangi to'lov xabari: {data}")

        payment_status = data.get("payment_status")
        payment_id = str(data.get("payment_id"))

        # Agar to'lov muvaffaqiyatli bo'lsa ('finished' yoki 'confirmed')
        if payment_status in ["finished", "confirmed"]:
            # 1. Buyurtmani topamiz
            order = await db.get_order_by_payment_id(payment_id)
            
            # Agar buyurtma bor bo'lsa va hali berilmagan bo'lsa
            if order and order['status'] != 'paid':
                # 2. Tovarni olamiz
                product = await db.get_product(order['product_id'])
                user_id = order['user_id']
                
                # 3. Foydalanuvchiga yuboramiz
                success_text = (
                    f"✅ **Оплата прошла успешно!**\n\n"
                    f"📦 **Ваш товар:**\n"
                    f"`{product['content']}`\n\n"
                    f"Спасибо за покупку!"
                )
                await bot.send_message(user_id, success_text, parse_mode="Markdown")
                
                # 4. Bazada statusni o'zgartiramiz
                await db.update_order_status(payment_id, 'paid')
                
                # Adminga xabar
                await bot.send_message(ADMIN_ID, f"💰 Sotildi! User: {user_id}, Summa: {order['amount_ltc']} LTC")
                
        return {"ok": True}
    except Exception as e:
        logging.error(f"IPN Error: {e}")
        return {"ok": False}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
