import asyncpg
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_conn()
    try:
        # Jadvallar
        await conn.execute('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, balance FLOAT DEFAULT 0.0, city TEXT DEFAULT 'bukhara', promo_used BOOLEAN DEFAULT FALSE, referral_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, title TEXT, price_usd FLOAT, content TEXT, city TEXT, is_sold BOOLEAN DEFAULT FALSE, content_type TEXT DEFAULT 'text', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, payment_id TEXT UNIQUE, user_id BIGINT, product_id INTEGER, amount_ltc FLOAT, status TEXT DEFAULT 'waiting', type TEXT DEFAULT 'product', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')

        # Migratsiya
        await conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS content_type TEXT DEFAULT 'text'")
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS promo_used BOOLEAN DEFAULT FALSE')
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_count INTEGER DEFAULT 0")
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'product'")
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        await conn.execute("UPDATE orders SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        
        await conn.execute('''INSERT INTO settings (key, value) VALUES ('main_image', 'https://cdn-icons-png.flaticon.com/512/3081/3081559.png') ON CONFLICT DO NOTHING''')
        logging.info("✅ Baza yangilandi.")
    finally:
        await conn.close()

# --- YANGI: TOP 5 XARIDORLAR ---
async def get_top_buyers():
    """Eng ko'p xarid qilgan 5 ta userni qaytaradi"""
    conn = await get_conn()
    try:
        rows = await conn.fetch('''
            SELECT u.username, u.user_id, COUNT(*) as count
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            WHERE o.status = 'paid' AND o.type = 'product'
            GROUP BY u.username, u.user_id
            ORDER BY count DESC
            LIMIT 5
        ''')
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(f"Top buyers error: {e}")
        return []
    finally: await conn.close()

# --- QOLGAN STATISTIKA FUNKSIYALARI ---
async def get_top_users_by_balance():
    conn = await get_conn()
    try:
        rows = await conn.fetch('SELECT user_id, username, balance, referral_count FROM users ORDER BY balance DESC LIMIT 10')
        return [dict(r) for r in rows]
    except: return []
    finally: await conn.close()

async def get_recent_sales_detailed():
    conn = await get_conn()
    try:
        rows = await conn.fetch('''
            SELECT o.created_at, u.username, u.user_id, p.title, p.price_usd 
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            JOIN products p ON o.product_id = p.id
            WHERE o.status = 'paid' AND o.type = 'product'
            ORDER BY o.created_at DESC
            LIMIT 10
        ''')
        return [dict(r) for r in rows]
    except: return []
    finally: await conn.close()

async def get_daily_stats():
    conn = await get_conn()
    try:
        row = await conn.fetchrow('''
            SELECT COUNT(*) as count, COALESCE(SUM(p.price_usd), 0) as total_usd
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.status = 'paid' AND o.type = 'product' AND o.created_at::date = CURRENT_DATE
        ''')
        return row['count'], row['total_usd']
    except: return 0, 0
    finally: await conn.close()

async def get_stats():
    conn = await get_conn()
    try:
        u = await conn.fetchval('SELECT COUNT(*) FROM users')
        b = await conn.fetchval('SELECT COALESCE(SUM(balance), 0) FROM users')
        s = await conn.fetchval('SELECT COUNT(*) FROM products WHERE is_sold = TRUE')
        return u, b, s
    except: return 0, 0, 0
    finally: await conn.close()

# --- QOLGAN FUNKSIYALAR ---
async def get_inventory_status():
    conn = await get_conn()
    try:
        rows = await conn.fetch('''SELECT city, title, COUNT(*) as count FROM products WHERE is_sold = FALSE GROUP BY city, title ORDER BY city, title''')
        return [dict(r) for r in rows]
    finally: await conn.close()

async def get_user_orders_with_content(user_id):
    conn = await get_conn()
    try:
        rows = await conn.fetch('''
            SELECT o.created_at, p.title, p.price_usd, p.content, p.content_type 
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            WHERE o.user_id = $1 AND o.status = 'paid' AND o.type = 'product' 
            ORDER BY o.created_at DESC LIMIT 10
        ''', user_id)
        return [dict(r) for r in rows]
    except: return []
    finally: await conn.close()

async def ensure_user(user_id, username):
    conn = await get_conn()
    try: await conn.execute('INSERT INTO users (user_id, username, promo_used, referral_count) VALUES ($1, $2, FALSE, 0) ON CONFLICT (user_id) DO UPDATE SET username = $2', user_id, username)
    finally: await conn.close()

async def check_user_exists(user_id):
    conn = await get_conn()
    try:
        val = await conn.fetchval('SELECT 1 FROM users WHERE user_id = $1', user_id)
        return val is not None
    finally: await conn.close()

async def get_user(user_id):
    conn = await get_conn()
    try: return dict(await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)) if user_id else None
    finally: await conn.close()

async def increment_referral(referrer_id):
    conn = await get_conn()
    try: await conn.execute('UPDATE users SET referral_count = referral_count + 1 WHERE user_id = $1', referrer_id)
    finally: await conn.close()

async def get_referral_count(user_id):
    conn = await get_conn()
    try:
        val = await conn.fetchval('SELECT referral_count FROM users WHERE user_id = $1', user_id)
        return val if val else 0
    finally: await conn.close()

async def get_grouped_products_by_city(city):
    conn = await get_conn()
    try:
        rows = await conn.fetch('''SELECT title, price_usd, COUNT(*) as count FROM products WHERE city = $1 AND is_sold = FALSE GROUP BY title, price_usd ORDER BY count DESC''', city)
        return [dict(r) for r in rows]
    finally: await conn.close()

async def get_one_product_by_title(title, city):
    conn = await get_conn()
    try:
        row = await conn.fetchrow('''SELECT * FROM products WHERE title = $1 AND city = $2 AND is_sold = FALSE LIMIT 1''', title, city)
        return dict(row) if row else None
    finally: await conn.close()

async def add_product_to_db(title, price, content, city, c_type):
    conn = await get_conn()
    try: await conn.execute('INSERT INTO products (title, price_usd, content, city, is_sold, content_type) VALUES ($1, $2, $3, $4, FALSE, $5)', title, price, content, city, c_type)
    finally: await conn.close()

async def delete_product_group(title, city):
    conn = await get_conn()
    try: await conn.execute('DELETE FROM products WHERE title = $1 AND city = $2 AND is_sold = FALSE', title, city)
    finally: await conn.close()

async def get_product(pid):
    conn = await get_conn()
    try: return dict(await conn.fetchrow('SELECT * FROM products WHERE id = $1', int(pid)))
    finally: await conn.close()

async def create_order(uid, pid, pay_id, amount, order_type='product'):
    conn = await get_conn()
    try:
        p_id = int(pid) if pid else None
        await conn.execute('INSERT INTO orders (user_id, product_id, payment_id, amount_ltc, status, type) VALUES ($1, $2, $3, $4, $5, $6)', uid, p_id, str(pay_id), float(amount), 'waiting', order_type)
    finally: await conn.close()

async def get_order_by_payment_id(pid):
    conn = await get_conn()
    try: return dict(await conn.fetchrow('SELECT * FROM orders WHERE payment_id = $1', str(pid)))
    finally: await conn.close()

async def update_order_status(pid, status):
    conn = await get_conn()
    try:
        await conn.execute('UPDATE orders SET status = $1 WHERE payment_id = $2', status, str(pid))
        if status == 'paid':
            row = await conn.fetchrow('SELECT product_id, type FROM orders WHERE payment_id = $1', str(pid))
            if row and row['type'] == 'product' and row['product_id']:
                await conn.execute('UPDATE products SET is_sold = TRUE WHERE id = $1', row['product_id'])
    finally: await conn.close()

async def get_all_users_ids():
    conn = await get_conn()
    try:
        rows = await conn.fetch('SELECT user_id FROM users')
        return [r['user_id'] for r in rows]
    finally: await conn.close()

async def update_user_city(user_id, city):
    conn = await get_conn()
    try: await conn.execute('UPDATE users SET city = $1 WHERE user_id = $2', city, user_id)
    finally: await conn.close()

async def set_promo_used(user_id, amount):
    conn = await get_conn()
    try: await conn.execute('UPDATE users SET balance = balance + $1, promo_used = TRUE WHERE user_id = $2', amount, user_id)
    finally: await conn.close()

async def admin_update_balance(user_id, amount):
    conn = await get_conn()
    try: await conn.execute('UPDATE users SET balance = balance + $1 WHERE user_id = $2', amount, user_id)
    finally: await conn.close()

async def add_balance(user_id, amount):
    conn = await get_conn()
    try: await conn.execute('UPDATE users SET balance = balance + $1 WHERE user_id = $2', amount, user_id)
    finally: await conn.close()

async def get_main_image():
    conn = await get_conn()
    try: return await conn.fetchval("SELECT value FROM settings WHERE key = 'main_image'")
    finally: await conn.close()

async def update_main_image(new_url):
    conn = await get_conn()
    try: await conn.execute("UPDATE settings SET value = $1 WHERE key = 'main_image'", new_url)
    finally: await conn.close()
