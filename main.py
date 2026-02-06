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

# Default rasm (agar bazada rasm bo'lmasa)
DEFAULT_IMAGE = "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- HOLATLAR (STATES) ---
class AddProduct(StatesGroup):
    title = State()
    price = State()
    city = State()
    content = State()

class UserState(StatesGroup):
    writing_review = State()    # Sharh yozish
    entering_promo = State()    # Promokod kiritish
    deposit_amount = State()    # Balans to'ldirish summasi

class AdminState(StatesGroup):
    change_balance_id = State()     # Qaysi user balansi?
    change_balance_amount = State() # Qancha summa?
    change_photo = State()          # Yangi rasm yuklash

# ----------------- LIFESPAN & WEBHOOK -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Bazani ishga tushiramiz
    await db.init_db()
    
    # 2. Webhookni ulaymiz
    webhook_url = f"{BASE_URL}/tg_webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook o'rnatildi: {webhook_url}")
    
    yield
    
    # 3. MUHIM: Bot to'xtaganda webhookni O'CHIRMAYMIZ!
    logging.info("Bot to'xtatildi, lekin Webhook qoldirildi (Connection uzilmasligi uchun).")

app = FastAPI(lifespan=lifespan)

# ----------------- TO'LOV TIZIMI (NOWPayments) -----------------
async def create_nowpayments_invoice(price_usd):
    url = "https://api.nowpayments.io/v1/payment"
    headers = {
        "x-api-key": NP_API_KEY,
        "Content-Type": "application/json"
    }
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

# ----------------- USER HANDLERS (Foydalanuvchi qismi) -----------------

@dp.message(CommandStart())
@dp.message(F.text == "🏠 Главное меню")
async def start(message: types.Message):
    # Userni bazaga yozish
    await db.ensure_user(message.from_user.id, message.from_user.username)
    
    # Rasmni bazadan olish
    current_image = await db.get_main_image()
    if not current_image:
        current_image = DEFAULT_IMAGE

    # Rasmni yuborish (Fayl ID yoki Link bo'lsa ham ishlaydi)
    try:
        await message.answer_photo(
            photo=current_image,
            caption="🏙 **Пожалуйста, выберите ваш город из списка:**",
            reply_markup=kb.kb_cities(),
            parse_mode="Markdown"
        )
    except:
        # Agar rasmda xatolik bo'lsa, default rasm ketadi
        await message.answer_photo(
            photo=DEFAULT_IMAGE,
            caption="🏙 **Пожалуйста, выберите ваш город из списка:**",
            reply_markup=kb.kb_cities(),
            parse_mode="Markdown"
        )

    # Pastdagi menyuni chiqarish
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

@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    text = (
        f"👤 **Твой id:** `{u['user_id']}`\n"
        f"🏙 **Твой город:** {u['city'].capitalize()}\n"
        f"🏧 **Баланс:** {u['balance']} $\n"
    )
    await call.message.edit_caption(caption=text, reply_markup=kb.kb_profile(), parse_mode="Markdown")

# --- PROMO KOD QISMI ---
@dp.callback_query(F.data == "enter_promo")
async def ask_promo(call: types.CallbackQuery, state: FSMContext):
    u = await db.get_user(call.from_user.id)
    if u.get('promo_used', False):
        await call.answer("❌ Вы уже использовали промокод!", show_alert=True)
        return
    await state.set_state(UserState.entering_promo)
    await call.message.answer("🎁 **Введите промокод:**")
    await call.answer()

@dp.message(UserState.entering_promo)
async def check_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code == "ESCO666":
        await db.set_promo_used(message.from_user.id, 5.0) # 5$ berish
        await message.answer("✅ **Поздравляем! Ваш баланс пополнен на 5$!**")
    else:
        await message.answer("❌ Неверный промокод.")
    await state.clear()
    # Menyuga qaytish
    await message.answer("🏠 Главное меню", reply_markup=kb.kb_reply_menu())

# --- BALANS TO'LDIRISH QISMI ---
@dp.callback_query(F.data == "deposit_balance")
async def ask_deposit(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.deposit_amount)
    await call.message.answer("💰 **Введите сумму пополнения в USD (например: 10):**")
    await call.answer()

@dp.message(UserState.deposit_amount)
async def create_deposit(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < 1:
            await message.answer("⚠️ Минимум 1 USD.")
            return

        msg = await message.answer("🔄 Генерирую счет для оплаты...")
        payment_data = await create_nowpayments_invoice(amount)
        
        if not payment_data:
            await msg.edit_text("❌ Ошибка платежной системы. Попробуйте позже.")
            await state.clear()
            return

        # Buyurtma yaratamiz (type='balance')
        await db.create_order(
            user_id=message.from_user.id, 
            product_id=None, 
            payment_id=payment_data['payment_id'], 
            amount_ltc=payment_data['pay_amount'], 
            order_type='balance'
        )
        
        text = (
            f"💰 **Пополнение баланса na {amount}$**\n"
            f"👇 Отправьте `{payment_data['pay_amount']}` LTC на адрес:\n"
            f"`{payment_data['pay_address']}`\n\n"
            f"⏳ После оплаты баланс пополнится автоматически."
        )
        # Manzilni alohida tashlaymiz
        await message.answer(payment_data['pay_address'])
        await msg.edit_text(text, parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Введите число (например: 10)")

# --- SOTIB OLISH (BUY) ---
@dp.callback_query(F.data.startswith("buy:"))
async def buy_start(call: types.CallbackQuery):
    product_id = call.data.split(":")[1]
    product = await db.get_product(product_id)
    u = await db.get_user(call.from_user.id)
    
    if not product:
        await call.answer("❌ Товар не найден!", show_alert=True)
        return

    # 1. BALANSDAN SOTIB OLISH
    if u['balance'] >= product['price_usd']:
        # Balansdan ayirish
        await db.admin_update_balance(call.from_user.id, -product['price_usd'])
        
        # Tovarni berish
        await call.message.delete()
        await call.message.answer(
            f"✅ **Покупка успешна!** (Списано с баланса)\n\n📦 **Ваш товар:**\n`{product['content']}`", 
            reply_markup=kb.kb_leave_review(), 
            parse_mode="Markdown"
        )
        
        # Bazada "Sotildi" deb belgilash
        conn = await db.get_conn()
        await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', int(product_id))
        await conn.close()
        
        # Adminga xabar
        await bot.send_message(ADMIN_ID, f"💰 SOTILDI (Balansdan)! Tovar: {product['title']}, User: {call.from_user.id}")
        return

    # 2. KRIPTO BILAN SOTIB OLISH (Agar balans yetmasa)
    await call.message.edit_caption(caption="🔄 **Генерирую адрес для оплаты...**", reply_markup=None, parse_mode="Markdown")

    payment_data = await create_nowpayments_invoice(product['price_usd'])
    
    if not payment_data:
        await call.message.answer("❌ Ошибка платежной системы.")
        return

    pay_address = payment_data['pay_address']
    pay_amount = payment_data['pay_amount']
    payment_id = payment_data['payment_id']

    # Buyurtma yaratamiz (type='product')
    await db.create_order(call.from_user.id, product_id, payment_id, pay_amount, order_type='product')

    text = (
        f"🛒 **Покупка:** {product['title']}\n"
        f"💵 **Цена:** {product['price_usd']} USD\n"
        f"⚠️ На балансе недостаточно средств. Оплатите криптой:\n\n"
        f"🔄 **К оплате:** `{pay_amount}` LTC\n"
        f"👇 **Адрес LTC:** `{pay_address}`\n\n"
        f"⏳ Бот автоматически выдаст товар после оплаты."
    )
    
    await call.message.answer(pay_address)
    await call.message.answer(text, reply_markup=kb.kb_back(), parse_mode="Markdown")

# ----------------- ADMIN PANEL (To'g'rilangan Rasm yuklash bilan) -----------------

@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Админ-панель v2.0:", reply_markup=kb.kb_admin())

# 1. Statistika
@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: types.CallbackQuery):
    users, total_money, sold = await db.get_stats()
    text = (
        f"📊 **Статистика бота:**\n\n"
        f"👥 Всего юзеров: {users}\n"
        f"💰 Общий баланс юзеров: {total_money} $\n"
        f"📦 Продано товаров: {sold} шт."
    )
    await call.message.edit_text(text, reply_markup=kb.kb_admin(), parse_mode="Markdown")

# 2. Balansni o'zgartirish
@dp.callback_query(F.data == "admin_balance")
async def admin_bal_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_balance_id)
    await call.message.edit_text("🆔 Введите ID пользователя:", reply_markup=None)

@dp.message(AdminState.change_balance_id)
async def admin_bal_id(message: types.Message, state: FSMContext):
    try:
        uid = int(message.text)
        await state.update_data(uid=uid)
        await state.set_state(AdminState.change_balance_amount)
        await message.answer("💰 Введите сумму (например: 10 yoki -5):")
    except:
        await message.answer("❌ ID raqam bo'lishi kerak.")

@dp.message(AdminState.change_balance_amount)
async def admin_bal_final(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()
        await db.admin_update_balance(data['uid'], amount)
        await message.answer(f"✅ User {data['uid']} balansi {amount}$ ga o'zgardi.")
        await state.clear()
        await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())
    except:
        await message.answer("❌ Summa xato.")

# 3. RASM O'ZGARTIRISH (Fayl va Link qabul qiladi)
@dp.callback_query(F.data == "admin_photo")
async def admin_photo_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_photo)
    await call.message.edit_text("🖼 **Menga rasm (.jpg) yuboring yoki rasmga havola (link) tashlang:**", reply_markup=None)

@dp.message(AdminState.change_photo)
async def admin_photo_save(message: types.Message, state: FSMContext):
    # Agar foydalanuvchi Rasm fayli yuborsa
    if message.photo:
        file_id = message.photo[-1].file_id # Eng tiniq versiyasini olamiz
        await db.update_main_image(file_id)
        await message.answer("✅ Rasm fayli saqlandi va yangilandi!")
        await state.clear()
        # Natijani ko'rsatamiz
        await message.answer_photo(file_id, caption="🛠 Yangi rasm:", reply_markup=kb.kb_admin())
        return

    # Agar foydalanuvchi Link yuborsa
    if message.text and message.text.startswith("http"):
        url = message.text.strip()
        await db.update_main_image(url)
        await message.answer("✅ Rasm havolasi (link) yangilandi!")
        await state.clear()
        # Natijani ko'rsatamiz
        await message.answer_photo(url, caption="🛠 Yangi rasm:", reply_markup=kb.kb_admin())
        return

    await message.answer("❌ Iltimos, rasm fayli yoki link yuboring.")

# 4. Tovar qo'shish
@dp.callback_query(F.data == "admin_add")
async def add_pr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.edit_text("1. Название товара:", reply_markup=None)

@dp.message(AddProduct.title)
async def add_pr_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("2. Цена (USD):")

@dp.message(AddProduct.price)
async def add_pr_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProduct.city)
        await message.answer("3. Город (bukhara/tashkent):")
    except: await message.answer("❌ Число введите!")

@dp.message(AddProduct.city)
async def add_pr_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.lower())
    await state.set_state(AddProduct.content)
    await message.answer("4. Контент (товар):")

@dp.message(AddProduct.content)
async def add_pr_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_product_to_db(data['title'], data['price'], message.text, data['city'])
    await state.clear()
    await message.answer("✅ Товар добавлен!", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "back_to_start")
async def back_to_menu_handler(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    
    current_image = await db.get_main_image()
    if not current_image: current_image = DEFAULT_IMAGE
    
    try:
        await call.message.answer_photo(current_image, "🏠 Главное меню:", reply_markup=kb.kb_main())
    except:
        await call.message.answer_photo(DEFAULT_IMAGE, "🏠 Главное меню:", reply_markup=kb.kb_main())

# --- OTZIVLAR (SHARHLAR) ---
@dp.callback_query(F.data == "write_review")
async def ask_review(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.writing_review)
    await call.message.answer("✍️ Напишите ваш отзыв:")
    await call.answer()

@dp.message(UserState.writing_review)
async def receive_review(message: types.Message, state: FSMContext):
    review = message.text
    user = message.from_user
    text = f"💬 **YANGI OTZIV!**\nUser: @{user.username} (ID: {user.id})\n\n📝: {review}"
    
    await bot.send_message(ADMIN_ID, text)
    await message.answer("✅ Отзыв отправлен админу. Спасибо!")
    await state.clear()
    
    # Qaytarish
    current_image = await db.get_main_image() or DEFAULT_IMAGE
    try:
        await message.answer_photo(current_image, "🏠 Меню:", reply_markup=kb.kb_main())
    except:
        await message.answer_photo(DEFAULT_IMAGE, "🏠 Меню:", reply_markup=kb.kb_main())


# ----------------- WEBHOOKS (IPN & TG) -----------------
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
        logging.info(f"IPN: {data}")
        
        if data.get("payment_status") in ["finished", "confirmed"]:
            payment_id = str(data.get("payment_id"))
            order = await db.get_order_by_payment_id(payment_id)
            
            if order and order['status'] != 'paid':
                # 1. Status yangilash
                await db.update_order_status(payment_id, 'paid')
                user_id = order['user_id']
                
                # 2. Buyurtma turi bo'yicha ajratish
                if order['type'] == 'product':
                    # Mahsulot berish
                    product = await db.get_product(order['product_id'])
                    await bot.send_message(
                        user_id, 
                        f"✅ Оплата прошла!\n📦 **Ваш товар:**\n`{product['content']}`", 
                        reply_markup=kb.kb_leave_review(), 
                        parse_mode="Markdown"
                    )
                    await bot.send_message(ADMIN_ID, f"💰 SOTILDI (Crypto)! Summa: {order['amount_ltc']} LTC")
                
                elif order['type'] == 'balance':
                    # Balansga pul qo'shish
                    # IPN da price_amount bu USD dagi summa
                    amount_usd = float(data.get('price_amount', 0))
                    await db.add_balance(user_id, amount_usd)
                    
                    await bot.send_message(user_id, f"✅ Баланс успешно пополнен на {amount_usd}$!")
                    await bot.send_message(ADMIN_ID, f"💰 BALANS TO'LDIRILDI! {amount_usd}$")

        return {"ok": True}
    except Exception as e:
        logging.error(f"IPN Error: {e}")
        return {"ok": False}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
