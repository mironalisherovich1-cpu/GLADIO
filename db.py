import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_conn()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0.0,
                city TEXT DEFAULT 'Bukhara',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT,
                price_usd FLOAT,
                content TEXT,
                city TEXT DEFAULT 'Bukhara',
                is_sold BOOLEAN DEFAULT FALSE
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                payment_id TEXT UNIQUE,
                user_id BIGINT,
                product_id INTEGER,
                amount_ltc FLOAT,
                status TEXT DEFAULT 'waiting'
            )
        ''')
    finally:
        await conn.close()

async def ensure_user(user_id: int, username: str):
    conn = await get_conn()
    try:
        await conn.execute('''
            INSERT INTO users (user_id, username) VALUES ($1, $2)
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

async def get_products_by_city(city: str):
    conn = await get_conn()
    try:
        rows = await conn.fetch('SELECT * FROM products WHERE city = $1 AND is_sold = FALSE', city)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def add_product_to_db(title, price, content, city):
    conn = await get_conn()
    try:
        await conn.execute('INSERT INTO products (title, price_usd, content, city) VALUES ($1, $2, $3, $4)', 
                           title, price, content, city)
    finally:
        await conn.close()
