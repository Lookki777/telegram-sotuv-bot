import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sales_bot.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Books table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price TEXT NOT NULL,
            channel_link TEXT,
            photo_id TEXT,
            is_active INTEGER DEFAULT 1
        )
        """)
        
        # Orders table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            username TEXT,
            book_id INTEGER NOT NULL,
            receipt_photo_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
        """)
        
        # Settings table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        # Set default payment details
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('payment_details', '💳 Uzcard / Humo: 8600 0000 0000 0000 (Click / Payme orqali to''lash mumkin)')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_link', 'https://t.me/+ExamplePrivateChannelLink')")
        
        conn.commit()

# --- Book Operations ---
def add_book(title, description, price, channel_link="", photo_id=""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO books (title, description, price, channel_link, photo_id) VALUES (?, ?, ?, ?, ?)",
            (title, description, price, channel_link, photo_id)
        )
        conn.commit()
        return cursor.lastrowid

def get_all_books(active_only=True):
    with get_db() as conn:
        cursor = conn.cursor()
        if active_only:
            rows = cursor.execute("SELECT * FROM books WHERE is_active = 1").fetchall()
        else:
            rows = cursor.execute("SELECT * FROM books").fetchall()
        return [dict(r) for r in rows]

def get_book(book_id):
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None

def delete_book(book_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET is_active = 0 WHERE id = ?", (book_id,))
        conn.commit()

# --- Order Operations ---
def create_order(user_id, user_name, username, book_id, receipt_photo_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, user_name, username, book_id, receipt_photo_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_name, username, book_id, receipt_photo_id)
        )
        conn.commit()
        return cursor.lastrowid

def update_order_status(order_id, status):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()

def get_order(order_id):
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None

# --- Settings Operations ---
def get_setting(key, default=""):
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else default

def set_setting(key, value):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
