import os
import logging
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject
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
    content = State() 

class UserState(StatesGroup):
    writing_review = State()
    entering_promo = State()
    deposit_amount = State()

class AdminState(StatesGroup):
    change_balance_id = State()
    change_balance_amount = State()
    change_photo = State()
    broadcast_msg = State() # Rassilka uchun

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

async def send_product_to_user(user_id, product):
    if product.get('content_type') == 'photo':
        await bot.send_photo(chat_id=user_id, photo=product['content'], caption=f"📦 **Tovaringiz:** {product['title']}", reply_markup=kb.kb_leave_review(), parse_mode="Markdown")
    else:
        await bot.send_message(chat_id=user_id, text=f"📦 **Tovaringiz:**\n\n`{product['content']}`", reply_markup=kb.kb_leave_review(), parse_mode="Markdown")

# --- START & REFERAL SYSTEM ---
@dp.message(CommandStart())
@dp.message(F.text == "🏠 Главное меню")
async def start(message: types.Message, command: CommandObject = None, state: FSMContext = None):
    if state: await state.clear()
    
    user_id = message.from_user.id
    
    # User oldin bormi?
    is_old_user = await db.check_user_exists(user_id)
    
    # Bazaga yozamiz
    await db.ensure_user(user_id, message.from_user.username)
    
    # Agar YANGI user bo'lsa va referal orqali kirgan bo'lsa
    if not is_old_user and command and command.args:
        try:
            referrer_id = int(command.args)
            # O'zini o'zi taklif qilolmaydi
            if referrer_id != user_id:
                await db.increment_referral(referrer_id)
                # Referrerga xabar
                try: await bot.send_message(referrer_id, f"🎉 Sizda yangi referal bor! ({message.from_user.full_name})")
                except: pass
        except: pass

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
    grouped = await db.get_grouped_products_by_city(u['city'])
    if not grouped: await call.answer("❌ Товаров пока нет", show_alert=True)
    else: await call.message.edit_caption(caption=f"🛒 **Товары ({u['city']}):**", reply_markup=kb.kb_shop(grouped), parse_mode="Markdown")

# --- PROFIL VA YANGILIKLAR ---
@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    ref_count = await db.get_referral_count(call.from_user.id)
    
    # Skidka foizini hisoblash
    if ref_count >= 10: skidka = 7
    elif ref_count >= 5: skidka = 5
    else: skidka = 0

    text = (
        f"👤 **Mening profilim:**\n"
        f"🆔 ID: `{u['user_id']}`\n"
        f"🏧 Balans: **{u['balance']} $**\n"
        f"👥 Takliflar: **{ref_count} ta**\n"
        f"📉 Mening skidkam: **{skidka}%**"
    )
    await call.message.edit_caption(caption=text, reply_markup=kb.kb_profile(), parse_mode="Markdown")

# 1. REFERAL PROGRAMMA
@dp.callback_query(F.data == "referral")
async def show_referral(call: types.CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    text = (
        "👥 **Referal Tizimi**\n\n"
        "Do'stlaringizni chaqiring va skidka oling!\n\n"
        "🔹 5 ta do'st = **5% skidka**\n"
        "🔹 10 ta do'st = **7% skidka**\n\n"
        f"🔗 **Sizning ssilkangiz:**\n`{ref_link}`"
    )
    await call.message.answer(text, reply_markup=kb.kb_back(), parse_mode="Markdown")
    await call.answer()

# 2. ISTORIYA POKUPOK
@dp.callback_query(F.data == "history")
async def show_history(call: types.CallbackQuery):
    orders = await db.get_user_orders(call.from_user.id)
    if not orders:
        await call.answer("❌ Siz hali hech narsa sotib olmagansiz.", show_alert=True)
        return
    
    text = "📜 **Xaridlar tarixi:**\n\n"
    for o in orders:
        date = o['created_at'].strftime("%Y-%m-%d %H:%M")
        text += f"📅 {date} | 📦 {o['title']} | 💰 {o['price_usd']}$\n"
    
    await call.message.answer(text, reply_markup=kb.kb_back(), parse_mode="Markdown")
    await call.answer()

# --- SOTIB OLISH (SKIDKA BILAN) ---
@dp.callback_query(F.data.startswith("buy_title:"))
async def buy_start_title(call: types.CallbackQuery):
    title = call.data.split("buy_title:")[1]
    u = await db.get_user(call.from_user.id)
    product = await db.get_one_product_by_title(title, u['city'])
    
    if not product:
        await call.answer("❌ Bu tovar tugagan!", show_alert=True)
        return

    # SKIDKA HISOBLASH
    ref_count = await db.get_referral_count(call.from_user.id)
    discount_percent = 0
    if ref_count >= 10: discount_percent = 7
    elif ref_count >= 5: discount_percent = 5
    
    original_price = product['price_usd']
    # Yangi narx
    final_price = original_price * (1 - discount_percent / 100)
    final_price = round(final_price, 2) # 2 xona yaxlitlash

    pid = str(product['id'])
    
    # 1. BALANS
    if u['balance'] >= final_price:
        await db.admin_update_balance(call.from_user.id, -final_price)
        await call.message.delete()
        await send_product_to_user(call.from_user.id, product)
        conn = await db.get_conn()
        await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', int(pid))
        await conn.close()
        await bot.send_message(ADMIN_ID, f"💰 SOTILDI (Balans): {product['title']} (Narx: {final_price}$)")
        return

    # 2. KRIPTO
    pd = await create_nowpayments_invoice(final_price)
    if pd:
        await db.create_order(call.from_user.id, pid, pd['payment_id'], pd['pay_amount'], 'product')
        
        # Narx haqida ma'lumot
        price_text = f"{original_price}$"
        if discount_percent > 0:
            price_text = f"~{original_price}$~ {final_price}$ (-{discount_percent}%)"
            
        await call.message.answer(
            f"🛒 **{product['title']}**\n💵 Narx: {price_text}\nTo'lang: `{pd['pay_amount']}` LTC\nAdres: `{pd['pay_address']}`", 
            reply_markup=kb.kb_back(), parse_mode="Markdown"
        )
        await call.message.answer(pd['pay_address'])

# --- ADMIN PANEL ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())

# RASSILKA (BROADCAST)
@dp.callback_query(F.data == "admin_broadcast")
async def admin_bc_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.broadcast_msg)
    await call.message.answer("📢 **Rassilka:**\nXabarni yuboring (Rasm+Text yoki faqat Text):", reply_markup=kb.kb_back())

@dp.message(AdminState.broadcast_msg)
async def admin_bc_send(message: types.Message, state: FSMContext):
    users = await db.get_all_users_ids()
    count = 0
    blocked = 0
    
    status_msg = await message.answer(f"⏳ Yuborilyapti... (Jami: {len(users)})")
    
    for uid in users:
        try:
            # Copy methodi xabarni (rasm, video, text) shundayligicha ko'chirib yuboradi
            await message.copy_to(chat_id=uid)
            count += 1
            await asyncio.sleep(0.05) # Spam bo'lmasligi uchun ozgina pauza
        except:
            blocked += 1
            
    await status_msg.edit_text(f"✅ **Rassilka tugadi!**\n\n📨 Yetib bordi: {count}\n🚫 Bloklaganlar: {blocked}")
    await state.clear()
    await message.answer("🛠 Admin panel:", reply_markup=kb.kb_admin())

# ... QOLGAN ADMIN FUNKSIYALARI O'ZGARISHLARSIZ ...
@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: types.CallbackQuery):
    u, b, s = await db.get_stats()
    await call.message.edit_text(f"📊 User: {u}\n💰 Balance: {b}\n📦 Sold: {s}", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_delete")
async def admin_delete_list(call: types.CallbackQuery):
    await call.message.edit_text("🏙 Qaysi shahardan?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Bukhara", callback_data="del_city:bukhara")],
        [InlineKeyboardButton(text="Tashkent", callback_data="del_city:tashkent")],
        [InlineKeyboardButton(text="⬅️ Nazad", callback_data="back_to_admin")]
    ]))

@dp.callback_query(F.data.startswith("del_city:"))
async def admin_delete_show_grp(call: types.CallbackQuery):
    city = call.data.split(":")[1]
    grouped = await db.get_grouped_products_by_city(city)
    if not grouped: return await call.answer("❌ Tovar yo'q", show_alert=True)
    await call.message.edit_text(f"🗑 {city.capitalize()} (Guruhlar):", reply_markup=kb.kb_admin_delete_list(grouped))

@dp.callback_query(F.data.startswith("del_grp:"))
async def admin_delete_final(call: types.CallbackQuery):
    title = call.data.split("del_grp:")[1]
    await db.delete_product_group(title, "bukhara") # Hozircha hardcode, agar aniq shahar kerak bo'lsa mantiqni o'zgartiramiz
    await db.delete_product_group(title, "tashkent")
    await call.answer("✅ O'chirildi!", show_alert=True)
    await admin_panel(call.message)

@dp.callback_query(F.data == "back_to_admin")
async def back_admin(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_add")
async def add_pr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.edit_text("1. Nomi:", reply_markup=kb.kb_back())

@dp.message(AddProduct.title)
async def add_title(m: types.Message, state: FSMContext):
    await state.update_data(title=m.text)
    await state.set_state(AddProduct.price)
    await m.answer("2. Narxi (USD):", reply_markup=kb.kb_back())

@dp.message(AddProduct.price)
async def add_price(m: types.Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text.replace(",", ".")))
        await state.set_state(AddProduct.city)
        await m.answer("3. Shahar (bukhara/tashkent):", reply_markup=kb.kb_back())
    except: await m.answer("❌ Son yozing!")

@dp.message(AddProduct.city)
async def add_city(m: types.Message, state: FSMContext):
    await state.update_data(city=m.text.lower())
    await state.set_state(AddProduct.content)
    await m.answer("4. TOVAR (Rasm/Matn):", reply_markup=kb.kb_back())

@dp.message(AddProduct.content)
async def add_content_finish(m: types.Message, state: FSMContext):
    data = await state.get_data()
    if m.photo: content, c_type = m.photo[-1].file_id, "photo"
    else: content, c_type = m.text, "text"
    await db.add_product_to_db(data['title'], data['price'], content, data['city'], c_type)
    await state.clear()
    await m.answer(f"✅ Tovar qo'shildi!", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_photo")
async def admin_ph(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_photo)
    await call.message.edit_text("📸 Rasm tashlang:", reply_markup=kb.kb_back())

@dp.message(AdminState.change_photo)
async def admin_ph_save(m: types.Message, state: FSMContext):
    fid = m.photo[-1].file_id if m.photo else m.text
    await db.update_main_image(fid)
    await state.clear()
    await m.answer_photo(fid, "Yangilandi!", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_balance")
async def admin_bal(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_balance_id)
    await call.message.edit_text("🆔 User ID:", reply_markup=kb.kb_back())

@dp.message(AdminState.change_balance_id)
async def admin_bal_id(m: types.Message, state: FSMContext):
    await state.update_data(uid=int(m.text))
    await state.set_state(AdminState.change_balance_amount)
    await m.answer("💰 Summa:", reply_markup=kb.kb_back())

@dp.message(AdminState.change_balance_amount)
async def admin_bal_save(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await db.admin_update_balance(d['uid'], float(m.text))
    await m.answer("✅ O'zgardi!", reply_markup=kb.kb_admin())
    await state.clear()

# --- QOLGAN CALLBACKLAR ---
@dp.callback_query(F.data == "enter_promo")
async def ask_promo(call: types.CallbackQuery, state: FSMContext):
    u = await db.get_user(call.from_user.id)
    if u.get('promo_used'): return await call.answer("❌ Использован!", show_alert=True)
    await state.set_state(UserState.entering_promo)
    await call.message.answer("🎁 Введите промокод:", reply_markup=kb.kb_back())

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
    await call.message.answer("💰 Сумма (USD):", reply_markup=kb.kb_back())

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

@dp.callback_query(F.data == "back_to_start")
async def back_to_start_handler(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    img = await db.get_main_image() or DEFAULT_IMAGE
    try: await call.message.answer_photo(img, "🏠 **Главное меню:**", reply_markup=kb.kb_main(), parse_mode="Markdown")
    except: await call.message.answer("🏠 **Главное меню:**", reply_markup=kb.kb_main())

@dp.callback_query(F.data == "write_review")
async def ask_review(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.writing_review)
    await call.message.answer("✍️ Напишите отзыв:")
    await call.answer()

@dp.message(UserState.writing_review)
async def receive_review(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"💬 OTZIV:\n{message.text}\nUser: @{message.from_user.username}")
    await message.answer("✅ Отзыв отправлен!")
    await state.clear()
    await start(message, None, state)

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
                    await send_product_to_user(o['user_id'], pr)
                    await bot.send_message(ADMIN_ID, f"💰 SOLD: {pr['title']}")
                elif o['type'] == 'balance':
                    amt = float(d.get('price_amount', 0))
                    await db.add_balance(o['user_id'], amt)
                    await bot.send_message(o['user_id'], f"✅ Balance +{amt}$")
        return {"ok": True}
    except: return {"ok": False}
