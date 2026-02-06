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

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
BASE_URL = os.getenv("BASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DEFAULT_IMAGE = "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddProduct(StatesGroup):
    title = State()
    price = State()
    city = State()
    content = State() # Rasm yoki matn shu yerda olinadi

class UserState(StatesGroup):
    writing_review = State()
    entering_promo = State()
    deposit_amount = State()

class AdminState(StatesGroup):
    change_balance_id = State()
    change_balance_amount = State()
    change_photo = State()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await bot.set_webhook(f"{BASE_URL}/tg_webhook")
    yield

app = FastAPI(lifespan=lifespan)

async def create_nowpayments_invoice(price_usd):
    url = "https://api.nowpayments.io/v1/payment"
    headers = {"x-api-key": NP_API_KEY, "Content-Type": "application/json"}
    data = {"price_amount": price_usd, "price_currency": "usd", "pay_currency": "ltc", "ipn_callback_url": f"{BASE_URL}/nowpayments/ipn"}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, headers=headers, json=data)
            return r.json() if r.status_code == 201 else None
        except: return None

# --- YORDAMCHI: TOVARNI MIJOZGA YUBORISH ---
async def send_product_to_user(user_id, product):
    # Agar tovar RASM bo'lsa (content_type='photo')
    if product.get('content_type') == 'photo':
        await bot.send_photo(
            chat_id=user_id,
            photo=product['content'],
            caption=f"📦 **Sizning tovaringiz:** {product['title']}\n\n✅ Xaridingiz uchun rahmat!",
            reply_markup=kb.kb_leave_review(),
            parse_mode="Markdown"
        )
    # Agar tovar MATN bo'lsa
    else:
        await bot.send_message(
            chat_id=user_id,
            text=f"📦 **Sizning tovaringiz:**\n\n`{product['content']}`\n\n✅ Xaridingiz uchun rahmat!",
            reply_markup=kb.kb_leave_review(),
            parse_mode="Markdown"
        )

# --- USER HANDLERS ---
@dp.message(CommandStart())
@dp.message(F.text == "🏠 Главное меню")
async def start(message: types.Message):
    await db.ensure_user(message.from_user.id, message.from_user.username)
    img = await db.get_main_image() or DEFAULT_IMAGE
    try: await message.answer_photo(img, "🏙 **Выберите город:**", reply_markup=kb.kb_cities(), parse_mode="Markdown")
    except: await message.answer_photo(DEFAULT_IMAGE, "🏙 **Выберите город:**", reply_markup=kb.kb_cities(), parse_mode="Markdown")
    if message.text == "/start": await message.answer("👇 Меню:", reply_markup=kb.kb_reply_menu())

@dp.callback_query(F.data.startswith("city:"))
async def select_city(call: types.CallbackQuery):
    await db.update_user_city(call.from_user.id, call.data.split(":")[1])
    await call.message.edit_caption(caption="✅ **Город выбран!**", reply_markup=kb.kb_main(), parse_mode="Markdown")

@dp.callback_query(F.data == "shop_list")
async def show_shop(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    products = await db.get_products_by_city(u['city'])
    if not products: await call.answer("❌ Товаров нет", show_alert=True)
    else: await call.message.edit_caption(caption=f"🛒 **Товары ({u['city']}):**", reply_markup=kb.kb_shop(products), parse_mode="Markdown")

@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    await call.message.edit_caption(caption=f"👤 ID: `{u['user_id']}`\n🏧 Баланс: {u['balance']} $", reply_markup=kb.kb_profile(), parse_mode="Markdown")

@dp.callback_query(F.data == "enter_promo")
async def ask_promo(call: types.CallbackQuery, state: FSMContext):
    u = await db.get_user(call.from_user.id)
    if u.get('promo_used'): return await call.answer("❌ Уже использован!", show_alert=True)
    await state.set_state(UserState.entering_promo)
    await call.message.answer("🎁 Введите промокод:")

@dp.message(UserState.entering_promo)
async def check_promo(message: types.Message, state: FSMContext):
    if message.text.strip() == "ESCO666":
        await db.set_promo_used(message.from_user.id, 5.0)
        await message.answer("✅ +5$!")
    else: await message.answer("❌ Ошибка.")
    await state.clear()
    await message.answer("🏠 Меню", reply_markup=kb.kb_reply_menu())

@dp.callback_query(F.data == "deposit_balance")
async def ask_deposit(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.deposit_amount)
    await call.message.answer("💰 Сумма (USD):")

@dp.message(UserState.deposit_amount)
async def create_deposit(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.replace(",", "."))
        pd = await create_nowpayments_invoice(amt)
        if pd:
            await db.create_order(message.from_user.id, None, pd['payment_id'], pd['pay_amount'], 'balance')
            await message.answer(f"💰 **Пополнение {amt}$**\nKripto: `{pd['pay_amount']}` LTC\nAdres: `{pd['pay_address']}`", parse_mode="Markdown")
        else: await message.answer("❌ Ошибка.")
    except: await message.answer("❌ Число!")
    await state.clear()

# --- BUY PRODUCT ---
@dp.callback_query(F.data.startswith("buy:"))
async def buy_start(call: types.CallbackQuery):
    pid = call.data.split(":")[1]
    pr = await db.get_product(pid)
    u = await db.get_user(call.from_user.id)
    if not pr: return await call.answer("❌ Netu!", show_alert=True)

    # Balansdan olish
    if u['balance'] >= pr['price_usd']:
        await db.admin_update_balance(call.from_user.id, -pr['price_usd'])
        await call.message.delete()
        
        # TOVARNI YUBORISH (Rasm yoki Matn)
        await send_product_to_user(call.from_user.id, pr)
        
        # Sotildi qilish
        conn = await db.get_conn()
        await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', int(pid))
        await conn.close()
        await bot.send_message(ADMIN_ID, f"💰 SOTILDI (Balance): {pr['title']}")
        return

    # Kripto
    pd = await create_nowpayments_invoice(pr['price_usd'])
    if pd:
        await db.create_order(call.from_user.id, pid, pd['payment_id'], pd['pay_amount'], 'product')
        await call.message.answer(f"🛒 **{pr['title']}**\n💵 {pr['price_usd']} USD\nTo'lang: `{pd['pay_amount']}` LTC\nAdres: `{pd['pay_address']}`", reply_markup=kb.kb_back(), parse_mode="Markdown")
        await call.message.answer(pd['pay_address'])

# --- ADMIN PANEL ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: types.CallbackQuery):
    u, b, s = await db.get_stats()
    await call.message.edit_text(f"📊 User: {u}\n💰 Balance: {b}\n📦 Sold: {s}", reply_markup=kb.kb_admin())

# 1. DELETE PRODUCT (YANGI)
@dp.callback_query(F.data == "admin_delete")
async def admin_delete_list(call: types.CallbackQuery):
    # Barcha shaharlar tovarlarini ko'rsatamiz (yoki so'rash mumkin, hozircha oddiy)
    # Keling, avval shaharni so'raymiz
    await call.message.edit_text("🏙 Qaysi shahardan o'chiramiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Bukhara", callback_data="del_city:bukhara")],
        [InlineKeyboardButton(text="Tashkent", callback_data="del_city:tashkent")],
        [InlineKeyboardButton(text="⬅️ Nazad", callback_data="back_to_admin")]
    ]))

@dp.callback_query(F.data.startswith("del_city:"))
async def admin_delete_show_pr(call: types.CallbackQuery):
    city = call.data.split(":")[1]
    prs = await db.get_products_by_city(city)
    if not prs:
        await call.answer("❌ Bu shaharda tovar yo'q", show_alert=True)
        return
    await call.message.edit_text(f"🗑 {city.capitalize()} - tanlang:", reply_markup=kb.kb_admin_delete_list(prs))

@dp.callback_query(F.data.startswith("del_pr:"))
async def admin_delete_final(call: types.CallbackQuery):
    pid = call.data.split(":")[1]
    await db.delete_product(pid)
    await call.answer("✅ Tovar o'chirildi!", show_alert=True)
    await admin_panel(call.message) # Adminga qaytish

@dp.callback_query(F.data == "back_to_admin")
async def back_admin(call: types.CallbackQuery):
    await call.message.edit_text("🛠 Админ-панель:", reply_markup=kb.kb_admin())

# 2. ADD PRODUCT (RASM QO'SHILDI)
@dp.callback_query(F.data == "admin_add")
async def add_pr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.edit_text("1. Nomini yozing:")

@dp.message(AddProduct.title)
async def add_title(m: types.Message, state: FSMContext):
    await state.update_data(title=m.text)
    await state.set_state(AddProduct.price)
    await m.answer("2. Narxi (USD):")

@dp.message(AddProduct.price)
async def add_price(m: types.Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text.replace(",", ".")))
        await state.set_state(AddProduct.city)
        await m.answer("3. Shahar (bukhara/tashkent):")
    except: await m.answer("❌ Son yozing!")

@dp.message(AddProduct.city)
async def add_city(m: types.Message, state: FSMContext):
    await state.update_data(city=m.text.lower())
    await state.set_state(AddProduct.content)
    await m.answer("4. TOVARNI YUKLANG:\n\n📸 **Rasm tashlang** (.jpg) - rasm boradi\n📝 **Yoki matn yozing** - matn boradi.")

@dp.message(AddProduct.content)
async def add_content_finish(m: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Rasm yuborildimi?
    if m.photo:
        content = m.photo[-1].file_id # Rasm ID si
        c_type = "photo"
        msg_text = "✅ Tovar (RASM) qo'shildi!"
    else:
        content = m.text # Matn
        c_type = "text"
        msg_text = "✅ Tovar (MATN) qo'shildi!"

    await db.add_product_to_db(data['title'], data['price'], content, data['city'], c_type)
    await state.clear()
    await m.answer(msg_text, reply_markup=kb.kb_admin())

# --- RASM VA BALANS SOZLAMALARI ---
@dp.callback_query(F.data == "admin_photo")
async def admin_ph(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_photo)
    await call.message.edit_text("📸 Rasm tashlang:")

@dp.message(AdminState.change_photo)
async def admin_ph_save(m: types.Message, state: FSMContext):
    fid = m.photo[-1].file_id if m.photo else m.text
    await db.update_main_image(fid)
    await m.answer("✅ Rasm o'zgardi!")
    await state.clear()
    await m.answer_photo(fid, "Admin Panel:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_balance")
async def admin_bal(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_balance_id)
    await call.message.edit_text("🆔 User ID:")

@dp.message(AdminState.change_balance_id)
async def admin_bal_id(m: types.Message, state: FSMContext):
    await state.update_data(uid=int(m.text))
    await state.set_state(AdminState.change_balance_amount)
    await m.answer("💰 Summa:")

@dp.message(AdminState.change_balance_amount)
async def admin_bal_save(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await db.admin_update_balance(d['uid'], float(m.text))
    await m.answer("✅ O'zgardi!", reply_markup=kb.kb_admin())
    await state.clear()

# --- WEBHOOKS ---
@app.post("/tg_webhook")
async def th(r: Request):
    try: await dp.feed_update(bot, types.Update.model_validate(await r.json(), context={"bot": bot}))
    except: pass
    return {"ok": True}

@app.post("/nowpayments/ipn")
async def ipn(r: Request):
    try:
        d = await r.json()
        if d.get("payment_status") in ["finished", "confirmed"]:
            pid = str(d.get("payment_id"))
            o = await db.get_order_by_payment_id(pid)
            if o and o['status'] != 'paid':
                await db.update_order_status(pid, 'paid')
                if o['type'] == 'product':
                    pr = await db.get_product(o['product_id'])
                    # TOVARNI YUBORISH (Rasm yoki Matn)
                    await send_product_to_user(o['user_id'], pr)
                    await bot.send_message(ADMIN_ID, f"💰 SOLD: {pr['title']}")
                elif o['type'] == 'balance':
                    amt = float(d.get('price_amount', 0))
                    await db.add_balance(o['user_id'], amt)
                    await bot.send_message(o['user_id'], f"✅ Balance +{amt}$")
        return {"ok": True}
    except: return {"ok": False}
