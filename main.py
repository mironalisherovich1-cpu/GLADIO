import os
import logging
import httpx
import asyncio
import html
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

# --- KONFIGURATSIYA ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
NP_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
BASE_URL = os.getenv("BASE_URL")

# 🔥 KO'P ADMINLARNI O'QISH
# Railwayda: 123456, 789012, 345678 kabi yozing
raw_admin_ids = os.getenv("ADMIN_ID", "0")
ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

# Agar hech kim bo'lmasa, xatolik chiqmasligi uchun 0 qo'shib qo'yamiz
if not ADMIN_IDS: ADMIN_IDS = [0]

# Otzivlar Kanali (-100 bilan)
REVIEW_CHANNEL_ID = -1003832779321

DEFAULT_IMAGE = "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- YORDAMCHI: ADMINLARGA XABAR YUBORISH ---
async def notify_admins(text):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except:
            pass # Agar biror admin botni bloklagan bo'lsa, kod to'xtab qolmaydi

# --- STATES ---
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
    broadcast_msg = State()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await bot.set_webhook(f"{BASE_URL}/tg_webhook")
    yield

app = FastAPI(lifespan=lifespan)

# --- TO'LOV ---
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
    caption = f"📦 <b>Ваш товар:</b> {html.escape(product['title'])}\n\n✅ Спасибо за покупку!"
    try:
        if product.get('content_type') == 'photo':
            await bot.send_photo(chat_id=user_id, photo=product['content'], caption=caption, reply_markup=kb.kb_leave_review(), parse_mode="HTML")
        else:
            await bot.send_message(chat_id=user_id, text=f"{caption}\n\n<code>{html.escape(product['content'])}</code>", reply_markup=kb.kb_leave_review(), parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error sending product: {e}")

# --- START & MENU ---
@dp.message(CommandStart())
@dp.message(F.text == "🏠 Главное меню")
async def start(message: types.Message, command: CommandObject = None, state: FSMContext = None):
    if state: await state.clear()
    user_id = message.from_user.id
    
    is_old_user = await db.check_user_exists(user_id)
    await db.ensure_user(user_id, message.from_user.username)
    
    if not is_old_user and command and command.args:
        try:
            referrer_id = int(command.args)
            if referrer_id != user_id:
                await db.increment_referral(referrer_id)
                try: await bot.send_message(referrer_id, f"🎉 У вас новый реферал! ({message.from_user.full_name})")
                except: pass
        except: pass

    img = await db.get_main_image() or DEFAULT_IMAGE
    try: await message.answer_photo(img, "🏙 <b>Выберите город:</b>", reply_markup=kb.kb_cities(), parse_mode="HTML")
    except: await message.answer_photo(DEFAULT_IMAGE, "🏙 <b>Выберите город:</b>", reply_markup=kb.kb_cities(), parse_mode="HTML")
    if message.text == "/start": await message.answer("👇 Меню активировано", reply_markup=kb.kb_reply_menu())

@dp.callback_query(F.data.startswith("city:"))
async def select_city(call: types.CallbackQuery):
    await db.update_user_city(call.from_user.id, call.data.split(":")[1])
    await call.message.edit_caption(caption="✅ <b>Город выбран!</b>", reply_markup=kb.kb_main(), parse_mode="HTML")

@dp.callback_query(F.data == "shop_list")
async def show_shop(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    grouped = await db.get_grouped_products_by_city(u['city'])
    if not grouped: await call.answer("❌ Товаров пока нет", show_alert=True)
    else: await call.message.edit_caption(caption=f"🛒 <b>Товары ({u['city'].capitalize()}):</b>", reply_markup=kb.kb_shop(grouped), parse_mode="HTML")

@dp.callback_query(F.data == "profile")
async def profile_view(call: types.CallbackQuery):
    u = await db.get_user(call.from_user.id)
    ref_count = await db.get_referral_count(call.from_user.id)
    if ref_count >= 10: skidka = 7
    elif ref_count >= 5: skidka = 5
    else: skidka = 0
    text = (f"👤 <b>Мой профиль:</b>\n🆔 ID: <code>{u['user_id']}</code>\n🏧 Баланс: <b>{u['balance']} $</b>\n👥 Приглашено: <b>{ref_count} чел.</b>\n📉 Моя скидка: <b>{skidka}%</b>")
    await call.message.edit_caption(caption=text, reply_markup=kb.kb_profile(), parse_mode="HTML")

@dp.callback_query(F.data == "referral")
async def show_referral(call: types.CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    text = ("👥 <b>Реферальная система</b>\n\nПриглашайте друзей и получайте скидки!\n\n🔹 5 друзей = <b>5% скидка</b>\n🔹 10 друзей = <b>7% скидка</b>\n\n" f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>")
    await call.message.answer(text, reply_markup=kb.kb_back(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "history")
async def show_history(call: types.CallbackQuery):
    orders = await db.get_user_orders_with_content(call.from_user.id)
    if not orders:
        await call.answer("❌ История пуста.", show_alert=True)
        return
    await call.message.answer("📜 <b>Ваши последние покупки (макс. 10):</b>", parse_mode="HTML")
    for o in orders:
        dt = o.get('created_at')
        date = dt.strftime("%Y-%m-%d %H:%M") if dt else "??:??"
        caption = f"📅 {date}\n📦 {html.escape(o['title'])} | 💰 {o['price_usd']}$"
        if o.get('content_type') == 'photo':
            await bot.send_photo(chat_id=call.from_user.id, photo=o['content'], caption=caption, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=call.from_user.id, text=f"{caption}\n\n<code>{html.escape(o['content'])}</code>", parse_mode="HTML")
        await asyncio.sleep(0.1)
    await call.message.answer("✅ Конец истории.", reply_markup=kb.kb_back())

@dp.callback_query(F.data.startswith("buy_title:"))
async def buy_start_title(call: types.CallbackQuery):
    title = call.data.split("buy_title:")[1]
    u = await db.get_user(call.from_user.id)
    product = await db.get_one_product_by_title(title, u['city'])
    if not product: return await call.answer("❌ Товар закончился!", show_alert=True)

    ref_count = await db.get_referral_count(call.from_user.id)
    discount_percent = 0
    if ref_count >= 10: discount_percent = 7
    elif ref_count >= 5: discount_percent = 5
    
    final_price = round(product['price_usd'] * (1 - discount_percent / 100), 2)
    pid = str(product['id'])
    
    if u['balance'] >= final_price:
        await db.admin_update_balance(call.from_user.id, -final_price)
        await call.message.delete()
        await send_product_to_user(call.from_user.id, product)
        conn = await db.get_conn()
        await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', int(pid))
        await conn.close()
        # HAMMA ADMINLARGA XABAR
        await notify_admins(f"💰 ПРОДАЖА (Баланс): {product['title']} (Цена: {final_price}$)")
        return

    pd = await create_nowpayments_invoice(final_price)
    if pd:
        await db.create_order(call.from_user.id, pid, pd['payment_id'], pd['pay_amount'], 'product')
        price_text = f"{product['price_usd']}$"
        if discount_percent > 0: price_text = f"~{product['price_usd']}$~ {final_price}$ (-{discount_percent}%)"
        await call.message.answer(f"🛒 <b>{product['title']}</b>\n💵 Цена: {price_text}\nОплатите: <code>{pd['pay_amount']}</code> LTC\nАдрес: <code>{pd['pay_address']}</code>", reply_markup=kb.kb_back(), parse_mode="HTML")
        await call.message.answer(pd['pay_address'])

# --- ADMIN PANEL (KO'P ADMINLAR UCHUN) ---
# F.from_user.id ADMIN_IDS ro'yxatida bo'lsa ishlaydi
@dp.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def admin_panel(message: types.Message):
    await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: types.CallbackQuery):
    try:
        u, b, s = await db.get_stats()
        today_count, today_usd = await db.get_daily_stats()
        recent_sales = await db.get_recent_sales_detailed()
        top_users = await db.get_top_users_by_balance()
        top_buyers = await db.get_top_buyers()
        
        text = (
            f"📊 <b>Статистика бота:</b>\n\n"
            f"📅 <b>СЕГОДНЯ:</b>\n   • Продано: <b>{today_count} шт</b>\n   • Прибыль: <b>{today_usd} $</b>\n\n"
            f"🌍 <b>ОБЩАЯ:</b>\n   • Юзеров: <b>{u}</b>\n   • Всего продаж: {s}\n   • Балансы юзеров: {b} $\n\n"
        )

        if top_users:
            text += "💎 <b>ТОП-10 БОГАЧЕЙ (Баланс):</b>\n"
            for i, user in enumerate(top_users, 1):
                 raw_name = user.get('username') or str(user['user_id'])
                 name = html.escape(raw_name) 
                 bal = user.get('balance', 0)
                 text += f"{i}. @{name} — {bal}$ (Ref: {user.get('referral_count', 0)})\n"
            text += "\n"

        if top_buyers:
            text += "🏆 <b>ТОП-5 ПОКУПАТЕЛЕЙ (Кол-во):</b>\n"
            for i, user in enumerate(top_buyers, 1):
                 raw_name = user.get('username') or str(user['user_id'])
                 name = html.escape(raw_name) 
                 count = user.get('count', 0)
                 text += f"{i}. @{name} — {count} шт\n"
            text += "\n"

        if recent_sales:
            text += "📝 <b>ПОСЛЕДНИЕ ПРОДАЖИ:</b>\n"
            for sale in recent_sales:
                dt = sale.get('created_at')
                time = dt.strftime("%H:%M") if dt else "--:--"
                raw_user = sale.get('username') or str(sale.get('user_id'))
                username = html.escape(raw_user)
                title = html.escape(sale['title'])
                text += f"🔹 {time} | @{username} | {title} ({sale['price_usd']}$)\n"

        await call.message.edit_text(text, reply_markup=kb.kb_admin(), parse_mode="HTML")
    except Exception as e:
        logging.error(f"Statistika xatosi: {e}")
        await call.answer(f"⚠️ Xatolik: {e}", show_alert=True)

@dp.callback_query(F.data == "admin_stock")
async def show_stock(call: types.CallbackQuery):
    items = await db.get_inventory_status()
    if not items:
        await call.answer("📦 Склад пуст!", show_alert=True)
        return
    text = "📦 <b>СКЛАД (Остаток):</b>\n\n"
    current_city = ""
    for item in items:
        if item['city'] != current_city:
            text += f"\n📍 <b>{item['city'].capitalize()}:</b>\n"
            current_city = item['city']
        text += f"   🔹 {item['title']}: <b>{item['count']} шт</b>\n"
    await call.message.edit_text(text, reply_markup=kb.kb_admin(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_broadcast")
async def admin_bc_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.broadcast_msg)
    await call.message.answer("📢 <b>Рассылка:</b>\nОтправьте сообщение (Фото/Текст/Видео):", reply_markup=kb.kb_back(), parse_mode="HTML")

@dp.message(AdminState.broadcast_msg)
async def admin_bc_send(message: types.Message, state: FSMContext):
    users = await db.get_all_users_ids()
    count, blocked = 0, 0
    status_msg = await message.answer(f"⏳ Отправка... (Всего: {len(users)})")
    for uid in users:
        try:
            await message.copy_to(chat_id=uid)
            count += 1
            await asyncio.sleep(0.05)
        except: blocked += 1
    await status_msg.edit_text(f"✅ <b>Рассылка завершена!</b>\n📨 Доставлено: {count}\n🚫 Блок: {blocked}", parse_mode="HTML")
    await state.clear()
    await message.answer("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_delete")
async def admin_delete_list(call: types.CallbackQuery):
    await call.message.edit_text("🏙 Выберите город:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Бухара", callback_data="del_city:bukhara")],
        [InlineKeyboardButton(text="Ташкент", callback_data="del_city:tashkent")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]))

@dp.callback_query(F.data.startswith("del_city:"))
async def admin_delete_show_grp(call: types.CallbackQuery):
    city = call.data.split(":")[1]
    grouped = await db.get_grouped_products_by_city(city)
    if not grouped: return await call.answer("❌ Пусто", show_alert=True)
    await call.message.edit_text(f"🗑 {city.capitalize()} (Группы):", reply_markup=kb.kb_admin_delete_list(grouped))

@dp.callback_query(F.data.startswith("del_grp:"))
async def admin_delete_final(call: types.CallbackQuery):
    title = call.data.split("del_grp:")[1]
    await db.delete_product_group(title, "bukhara")
    await db.delete_product_group(title, "tashkent")
    await call.answer("✅ Удалено!", show_alert=True)
    await admin_panel(call.message)

@dp.callback_query(F.data == "back_to_admin")
async def back_admin(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 Админ-панель:", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_add")
async def add_pr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.title)
    await call.message.edit_text("1. Название:", reply_markup=kb.kb_back())

@dp.message(AddProduct.title)
async def add_title(m: types.Message, state: FSMContext):
    await state.update_data(title=m.text)
    await state.set_state(AddProduct.price)
    await m.answer("2. Цена (USD):", reply_markup=kb.kb_back())

@dp.message(AddProduct.price)
async def add_price(m: types.Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text.replace(",", ".")))
        await state.set_state(AddProduct.city)
        await m.answer("3. Город (bukhara/tashkent):", reply_markup=kb.kb_back())
    except: await m.answer("❌ Введите число!")

@dp.message(AddProduct.city)
async def add_city(m: types.Message, state: FSMContext):
    await state.update_data(city=m.text.lower())
    await state.set_state(AddProduct.content)
    await m.answer("4. ТОВАР (Фото/Текст):", reply_markup=kb.kb_back())

@dp.message(AddProduct.content)
async def add_content_finish(m: types.Message, state: FSMContext):
    data = await state.get_data()
    if m.photo: content, c_type = m.photo[-1].file_id, "photo"
    else: content, c_type = m.text, "text"
    await db.add_product_to_db(data['title'], data['price'], content, data['city'], c_type)
    await state.clear()
    await m.answer(f"✅ Товар добавлен!", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_photo")
async def admin_ph(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_photo)
    await call.message.edit_text("📸 Отправьте фото:", reply_markup=kb.kb_back())

@dp.message(AdminState.change_photo)
async def admin_ph_save(m: types.Message, state: FSMContext):
    fid = m.photo[-1].file_id if m.photo else m.text
    await db.update_main_image(fid)
    await state.clear()
    await m.answer_photo(fid, "Обновлено!", reply_markup=kb.kb_admin())

@dp.callback_query(F.data == "admin_balance")
async def admin_bal(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.change_balance_id)
    await call.message.edit_text("🆔 ID юзера:", reply_markup=kb.kb_back())

@dp.message(AdminState.change_balance_id)
async def admin_bal_id(m: types.Message, state: FSMContext):
    await state.update_data(uid=int(m.text))
    await state.set_state(AdminState.change_balance_amount)
    await m.answer("💰 Сумма (например 10):", reply_markup=kb.kb_back())

@dp.message(AdminState.change_balance_amount)
async def admin_bal_save(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await db.admin_update_balance(d['uid'], float(m.text))
    await m.answer("✅ Баланс изменен!", reply_markup=kb.kb_admin())
    await state.clear()

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
    await message.answer("🏠 Главное меню", reply_markup=kb.kb_reply_menu())

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
            await message.answer(f"💰 <b>Пополнение {amt}$</b>\nКрипто: <code>{pd['pay_amount']}</code> LTC\nАдрес: <code>{pd['pay_address']}</code>", parse_mode="HTML")
        else: await message.answer("❌ Ошибка.")
    except: await message.answer("❌ Число!")
    await state.clear()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start_handler(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    img = await db.get_main_image() or DEFAULT_IMAGE
    try: await call.message.answer_photo(img, "🏠 <b>Главное меню:</b>", reply_markup=kb.kb_main(), parse_mode="HTML")
    except: await call.message.answer("🏠 <b>Главное меню:</b>", reply_markup=kb.kb_main(), parse_mode="HTML")

@dp.callback_query(F.data == "write_review")
async def ask_review(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.writing_review)
    await call.message.answer("✍️ Напишите ваш отзыв (Текст/Фото):", reply_markup=kb.kb_back())
    await call.answer()

@dp.message(UserState.writing_review)
async def receive_review(message: types.Message, state: FSMContext):
    try:
        await bot.copy_message(chat_id=REVIEW_CHANNEL_ID, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer("✅ Отзыв опубликован в канале! Спасибо!")
    except Exception as e:
        logging.error(f"Kanal xatoligi: {e}")
        await notify_admins(f"⚠️ Kanalga xabar yuborishda xato: {e}")
        await message.answer("✅ Отзыв отправлен администратору!")
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
                    # HAMMA ADMINLARGA XABAR
                    await notify_admins(f"💰 ПРОДАЖА (Крипто): {pr['title']} (Цена: {o['amount_ltc']} LTC)")
                elif o['type'] == 'balance':
                    amt = float(d.get('price_amount', 0))
                    await db.add_balance(o['user_id'], amt)
                    await bot.send_message(o['user_id'], f"✅ Баланс пополнен +{amt}$")
        return {"ok": True}
    except: return {"ok": False}
