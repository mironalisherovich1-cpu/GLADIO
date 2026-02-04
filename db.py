import asyncpg
import os
import logging

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_conn()
    try:
        # Таблица пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Таблица товаров
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT,
                price_usd FLOAT,
                content TEXT,
                is_sold BOOLEAN DEFAULT FALSE
            )
        ''')
        # Таблица заказов
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
        logging.info("База данных готова.")
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

async def create_order(payment_id: str, user_id: int, product_id: int, amount: float):
    conn = await get_conn()
    try:
        await conn.execute('''
            INSERT INTO orders (payment_id, user_id, product_id, amount_ltc)
            VALUES ($1, $2, $3, $4)
        ''', payment_id, user_id, product_id, amount)
    finally:
        await conn.close()

async def get_order_by_payment(payment_id: str):
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM orders WHERE payment_id = $1', payment_id)
        return dict(row) if row else None
    finally:
        await conn.close()

async def set_order_status(payment_id: str, status: str):
    conn = await get_conn()
    try:
        await conn.execute('UPDATE orders SET status = $1 WHERE payment_id = $2', status, payment_id)
    finally:
        await conn.close()

async def get_product(product_id: int):
    conn = await get_conn()
    try:
        row = await conn.fetchrow('SELECT * FROM products WHERE id = $1', product_id)
        return dict(row) if row else None
    finally:
        await conn.close()
