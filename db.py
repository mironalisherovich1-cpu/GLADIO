import asyncpg
import os
import logging

# Xatolarni ko'rish uchun log
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    """Baza bilan ulanish yaratish"""
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """
    Jadvallarni yaratish.
    Bu funksiya bot har safar ishga tushganda ishlaydi va 
    agar jadvallar yo'q bo'lsa, ularni yaratadi.
    """
    conn = await get_conn()
    try:
        # 1. FOYDALANUVCHILAR JADVALI
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0.0,
                city TEXT DEFAULT 'bukhara',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. MAHSULOTLAR JADVALI
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT,
                price_usd FLOAT,
                content TEXT,
                city TEXT,
                is_sold BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. BUYURTMALAR (ORDER) JADVALI
        # payment_id - NOWPayments bergan ID
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                payment_id TEXT UNIQUE,
                user_id BIGINT,
                product_id INTEGER,
                amount_ltc FLOAT,
                status TEXT DEFAULT 'waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logging.info("✅ Bazadagi jadvallar tekshirildi/yaratildi.")
    except Exception as e:
        logging.error(f"❌ Baza yaratishda xatolik: {e}")
    finally:
        await conn.close()

# ----------------- USER FUNKSIYALARI -----------------

async def ensure_user(user_id: int, username: str):
    """Foydalanuvchini bazaga qo'shish (agar oldin bo'lmasa)"""
    conn = await get_conn()
    try:
        await conn.execute('''
            INSERT INTO users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET username = $2
        ''', user_id, username)
    finally:
        await conn.close()

async def get_user(user_id: int):
    """Foydalanuvchi ma'lumotlarini olish"""
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
        return dict(row) if row else None
    finally:
        await conn.close()

async def update_user_city(user_id: int, city: str):
    """Foydalanuvchi tanlagan shaharni yangilash"""
    conn = await get_conn()
    try:
        await conn.execute('UPDATE users SET city = $1 WHERE user_id = $2', city, user_id)
    finally:
        await conn.close()

# ----------------- MAHSULOT FUNKSIYALARI -----------------

async def add_product_to_db(title, price, content, city):
    """Yangi mahsulot qo'shish"""
    conn = await get_conn()
    try:
        await conn.execute('''
            INSERT INTO products (title, price_usd, content, city, is_sold) 
            VALUES ($1, $2, $3, $4, FALSE)
        ''', title, price, content, city)
    finally:
        await conn.close()

async def get_products_by_city(city: str):
    """
    Shahar bo'yicha sotilmagan (is_sold=FALSE) tovarlarni olish.
    """
    conn = await get_conn()
    try:
        # Faqat sotilmagan tovarlarni chiqaramiz
        rows = await conn.fetch('''
            SELECT * FROM products 
            WHERE city = $1 AND is_sold = FALSE 
            ORDER BY id DESC
        ''', city)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_product(product_id):
    """ID orqali bitta tovarni olish"""
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM products WHERE id = $1', int(product_id))
        return dict(row) if row else None
    finally:
        await conn.close()

# ----------------- BUYURTMA VA TO'LOV FUNKSIYALARI -----------------

async def create_order(user_id, product_id, payment_id, amount_ltc):
    """Yangi buyurtma yaratish (status: waiting)"""
    conn = await get_conn()
    try:
        await conn.execute('''
            INSERT INTO orders (user_id, product_id, payment_id, amount_ltc, status)
            VALUES ($1, $2, $3, $4, 'waiting')
        ''', user_id, int(product_id), str(payment_id), float(amount_ltc))
    finally:
        await conn.close()

async def get_order_by_payment_id(payment_id):
    """Payment ID orqali buyurtmani topish (IPN uchun)"""
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM orders WHERE payment_id = $1', str(payment_id))
        return dict(row) if row else None
    finally:
        await conn.close()

async def update_order_status(payment_id, status):
    """
    Buyurtma statusini yangilash.
    Agar status 'paid' bo'lsa, mahsulotni ham 'sotildi' (is_sold=TRUE) deb belgilaymiz.
    """
    conn = await get_conn()
    try:
        # 1. Order statusini yangilash
        await conn.execute('UPDATE orders SET status = $1 WHERE payment_id = $2', status, str(payment_id))
        
        # 2. Agar to'lov bo'lgan bo'lsa, mahsulotni bazadan "o'chiramiz" (sotildi qilamiz)
        if status == 'paid':
            # Avval orderdan product_id ni olamiz
            row = await conn.fetchrow('SELECT product_id FROM orders WHERE payment_id = $1', str(payment_id))
            if row:
                product_id = row['product_id']
                await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', product_id)
                
    finally:
        await conn.close()
