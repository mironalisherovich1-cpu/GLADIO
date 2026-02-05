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

IMAGE_URL = "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Admin va User holatlari
class AddProduct(StatesGroup):
    title = State()
    price = State()
    city = State()
    content = State()

class UserState(StatesGroup):
    writing_review = State() # Sharh yozish holati

# ----------------- LIFESPAN -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    webhook_url = f"{BASE_URL}/tg_webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook o'rnatildi: {webhook_url}")
    yield
    logging.info("Bot to'xtatildi, Webhook o'chirilmay qoldirildi.")

app = FastAPI(lifespan=lifespan)

async def create_nowpayments_invoice(price_usd):
    url = "https://api.nowpayments.io/v1/payment"
    headers = {"x-api-key": NP_API_KEY, "Content-Type": "application/json"}
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
            return None
        except:
            return None

# ----------------- USER HANDLERS -----------------

# /start bosilganda yoki pastdagi "🏠 Главное меню" bosilganda
@dp.message(CommandStart())
@dp.message(F.text == "🏠 Главное меню")
async def start(message: types.Message):
    await db.ensure_user(message.from_user.id, message.from_user.username)
    
    # Rasm va Inline tugmalar
    await message.answer_photo(
        photo=IMAGE_URL,
        caption="🏙 **Пожалуйста, выберите ваш город из списка:**",
        reply_markup=kb.kb_cities(),
        parse_mode="Markdown"
    )
    
    # Pastdagi doimiy tugmani chiqarish (faqat /start da yoki menyuda)
    if message.text == "/start":
        await message.answer("👇 Меню снизу активировано", reply_markup=kb.kb_reply_menu())

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

# --- SOTIB OLISH LOGIKASI ---
@dp.callback_query(F.data.startswith("buy:"))
async def buy_start(call: types.CallbackQuery):
    product_id = call.data.split(":")[1]
    product = await db.get_product(product_id)
    
    if not product:
        await call.answer("❌ Товар не найден!", show_alert=True)
        return

    await call.message.edit_caption(caption="🔄 **Генерирую адрес для оплаты...**", reply_markup=None, parse_mode="Markdown")

    payment_data = await create_nowpayments_invoice(product['price_usd'])
    if not payment_data:
        await call.message.answer("❌ Ошибка платежной системы.")
        return

    pay_address = payment_data['pay_address']
    pay_amount = payment_data['pay_amount']
    payment_id = payment_data['payment_id']

    await db.create_order(call.from_user.id, product_id, payment_id, pay_amount)

    text = (
        f"🛒 **Покупка:** {product['title']}\n"
        f"💵 **Стоимость:** {product['price_usd']} USD\n"
        f"🔄 **К оплате:** `{pay_amount}` LTC\n\n"
        f"👇 **Отправьте точную сумму на этот адрес:**\n"
        f"`{pay_address}`\n\n"
        f"⏳ **После оплаты бот АВТОМАТИЧЕСКИ пришлет вам товар.**"
    )
    
    await call.message.answer(pay_address)
    await call.message.answer(text, reply_markup=kb.kb_back(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_start")
async def back_to_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear() # Har ehtimolga qarshi holatni tozalaymiz
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

# --- SHARH QOLDIRISH (OTZIV) ---
@dp.callback_query(F.data == "write_review")
async def ask_review(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.writing_review)
    await call.message.answer("✍️ **Напишите ваш отзыв о товаре:**\n(Текст, который вы отправите, увидит администратор)")
    await call.answer()

@dp.message(UserState.writing_review)
async def receive_review(message: types.Message, state: FSMContext):
    review_text = message.text
    user = message.from_user
    
    # Adminga yuborish
    admin_text = (
        f"💬 **НОВЫЙ ОТЗЫВ!**\n\n"
        f"👤 От: {user.full_name} (@{user.username})\n"
        f"🆔 ID: `{user.id}`\n\n"
        f"📝 **Отзыв:**\n{review_text}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text)
        await message.answer("✅ **Спасибо! Ваш отзыв отправлен администратору.**")
    except:
        await message.answer("✅ Спасибо за отзыв!")
        
    await state.clear()
    # Menyuga qaytaramiz
    await message.answer("🏠 Главное меню:", reply_markup=kb.kb_main())


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
        await message.answer("❌ Ошибка! Число (10.5)")

@dp.message(AddProduct.city)
async def add_pr_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await state.set_state(AddProduct.content)
    await message.answer("4. Введите контент:")

@dp.message(AddProduct.content)
async def add_pr_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product_to_db(data['title'], data['price'], message.text, data['city'])
    await state.clear()
    await message.answer("✅ Товар добавлен!")

# ----------------- WEBHOOKS & IPN -----------------
@app.post("/tg_webhook")
async def tg_webhook(request: Request):
    try:
        update = types.Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logging.error(f"Telegram Webhook Error: {e}")
    return {"ok": True}

@app.post("/nowpayments/ipn")
async def ipn_webhook(request: Request):
    try:
        data = await request.json()
        payment_status = data.get("payment_status")
        payment_id = str(data.get("payment_id"))

        if payment_status in ["finished", "confirmed"]:
            order = await db.get_order_by_payment_id(payment_id)
            if order and order['status'] != 'paid':
                product = await db.get_product(order['product_id'])
                user_id = order['user_id']
                
                # Tovarni berish + SHARH TUGMASI
                success_text = (
                    f"✅ **Оплата прошла успешно!**\n\n"
                    f"📦 **Ваш товар:**\n`{product['content']}`\n\n"
                    f"🙏 Пожалуйста, оставьте отзыв, если вам не сложно!"
                )
                
                # Bu yerda kb.kb_leave_review() ishlatamiz
                await bot.send_message(user_id, success_text, reply_markup=kb.kb_leave_review(), parse_mode="Markdown")
                
                await db.update_order_status(payment_id, 'paid')
                await bot.send_message(ADMIN_ID, f"💰 Sotildi! {order['amount_ltc']} LTC")
                
        return {"ok": True}
    except Exception as e:
        logging.error(f"IPN Error: {e}")
        return {"ok": False}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
