import asyncpg
import os
import logging

# Loglarni yoqish
logging.basicConfig(level=logging.INFO)
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    """Baza bilan ulanish"""
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """
    Jadvallarni yaratish va YANGILASH (Migration)
    Bu funksiya baza eski bo'lsa ham, unga yangi ustunlarni o'zi qo'shadi.
    """
    conn = await get_conn()
    try:
        # 1. Jadvallarni yaratish (Agar ular umuman yo'q bo'lsa)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0.0,
                city TEXT DEFAULT 'bukhara',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # ---------------------------------------------------------
        # 🔥 "SMART" YANGILASH QISMI (Eng muhim joyi)
        # Agar eski bazada bu ustunlar yo'q bo'lsa, kod ularni o'zi qo'shadi.
        # ---------------------------------------------------------

        # Users jadvaliga 'promo_used' qo'shish
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS promo_used BOOLEAN DEFAULT FALSE')
        
        # Orders jadvaliga 'type' (turi) qo'shish
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'product'")

        # Boshlang'ich rasm (agar yo'q bo'lsa)
        await conn.execute('''
            INSERT INTO settings (key, value) 
            VALUES ('main_image', 'https://cdn-icons-png.flaticon.com/512/3081/3081559.png')
            ON CONFLICT DO NOTHING
        ''')
        
        logging.info("✅ Baza MUVAFFAQIYATLI yangilandi (Smart Update).")

    except Exception as e:
        logging.error(f"❌ Baza xatoligi: {e}")
    finally:
        await conn.close()

# ----------------- 1. USER FUNKSIYALARI -----------------

async def ensure_user(user_id: int, username: str):
    conn = await get_conn()
    try:
        # promo_used default FALSE bo'ladi
        await conn.execute('''
            INSERT INTO users (user_id, username, promo_used) VALUES ($1, $2, FALSE)
            ON CONFLICT (user_id) DO UPDATE SET username = $2
        ''', user_id, username)
    finally:
        await conn.close()

async def get_user(user_id: int):
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
        return dict(row) if row else None
    finally:
        await conn.close()

async def update_user_city(user_id: int, city: str):
    conn = await get_conn()
    try:
        await conn.execute('UPDATE users SET city = $1 WHERE user_id = $2', city, user_id)
    finally:
        await conn.close()

# ----------------- 2. PROMO VA BALANS -----------------

async def set_promo_used(user_id: int, amount: float):
    conn = await get_conn()
    try:
        # Balansga pul qo'shish va promoni ishlatildi deb belgilash
        await conn.execute('UPDATE users SET balance = balance + $1, promo_used = TRUE WHERE user_id = $2', amount, user_id)
    finally:
        await conn.close()

async def admin_update_balance(user_id: int, amount: float):
    conn = await get_conn()
    try:
        # Admin balansni o'zgartirishi
        await conn.execute('UPDATE users SET balance = balance + $1 WHERE user_id = $2', amount, user_id)
    finally:
        await conn.close()

async def add_balance(user_id: int, amount: float):
    conn = await get_conn()
    try:
        # Avtomatik to'lovdan keyin balans qo'shish
        await conn.execute('UPDATE users SET balance = balance + $1 WHERE user_id = $2', amount, user_id)
    finally:
        await conn.close()

# ----------------- 3. STATISTIKA VA SETTINGS -----------------

async def get_stats():
    conn = await get_conn()
    try:
        user_count = await conn.fetchval('SELECT COUNT(*) FROM users')
        # Agar balans NULL bo'lsa 0 deb olamiz
        total_balance = await conn.fetchval('SELECT COALESCE(SUM(balance), 0) FROM users')
        sold_products = await conn.fetchval('SELECT COUNT(*) FROM products WHERE is_sold = TRUE')
        return user_count, total_balance, sold_products
    finally:
        await conn.close()

async def get_main_image():
    conn = await get_conn()
    try:
        return await conn.fetchval("SELECT value FROM settings WHERE key = 'main_image'")
    finally:
        await conn.close()

async def update_main_image(new_url: str):
    conn = await get_conn()
    try:
        await conn.execute("UPDATE settings SET value = $1 WHERE key = 'main_image'", new_url)
    finally:
        await conn.close()

# ----------------- 4. MAHSULOTLAR -----------------

async def add_product_to_db(title, price, content, city):
    conn = await get_conn()
    try:
        await conn.execute('''
            INSERT INTO products (title, price_usd, content, city, is_sold) 
            VALUES ($1, $2, $3, $4, FALSE)
        ''', title, price, content, city)
    finally:
        await conn.close()

async def get_products_by_city(city: str):
    conn = await get_conn()
    try:
        rows = await conn.fetch('''
            SELECT * FROM products 
            WHERE city = $1 AND is_sold = FALSE 
            ORDER BY id DESC
        ''', city)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_product(product_id):
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM products WHERE id = $1', int(product_id))
        return dict(row) if row else None
    finally:
        await conn.close()

# ----------------- 5. BUYURTMALAR (ORDERS) -----------------

async def create_order(user_id, product_id, payment_id, amount_ltc, order_type='product'):
    conn = await get_conn()
    try:
        # Agar balans to'ldirish bo'lsa, product_id NULL bo'ladi
        pid = int(product_id) if product_id else None
        
        await conn.execute('''
            INSERT INTO orders (user_id, product_id, payment_id, amount_ltc, status, type)
            VALUES ($1, $2, $3, $4, 'waiting', $5)
        ''', user_id, pid, str(payment_id), float(amount_ltc), order_type)
    finally:
        await conn.close()

async def get_order_by_payment_id(payment_id):
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM orders WHERE payment_id = $1', str(payment_id))
        return dict(row) if row else None
    finally:
        await conn.close()

async def update_order_status(payment_id, status):
    conn = await get_conn()
    try:
        # Statusni yangilash
        await conn.execute('UPDATE orders SET status = $1 WHERE payment_id = $2', status, str(payment_id))
        
        # Agar to'landi bo'lsa va bu mahsulot bo'lsa, uni bazadan "sotildi" deb belgilaymiz
        if status == 'paid':
            row = await conn.fetchrow('SELECT product_id, type FROM orders WHERE payment_id = $1', str(payment_id))
            if row and row['type'] == 'product' and row['product_id']:
                await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', row['product_id'])
                
    finally:
        await conn.close()
