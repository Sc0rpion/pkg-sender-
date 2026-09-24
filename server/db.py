"""
Модуль работы с NoSQL хранилищем на базе SQLite.
"""
import sqlite3
import json
import os
from logger import logger

DB_PATH = os.path.join(os.path.dirname(__file__), 'catalog.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, data TEXT)''')
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def save_game(game_id, data_dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO games (id, data) VALUES (?, ?)", (game_id, json.dumps(data_dict)))
    conn.commit()
    conn.close()
    logger.info(f"Saved game to DB: {game_id}")

def get_all_catalog():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data FROM games")
    rows = c.fetchall()
    conn.close()
    return [json.loads(row[0])["catalog"] for row in rows]

def get_game(game_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data FROM games WHERE id=?", (game_id,))
    row = c.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def game_exists_and_unchanged(file_path, current_size):
    """
    Проверяет, есть ли игра в БД и совпадает ли ее физический размер.
    Если размер изменился (например, файл докачался), вернет False для повторного парсинга.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT json_extract(data, '$.catalog.size') FROM games WHERE json_extract(data, '$.local_pkg') = ?", (file_path,))
    row = c.fetchone()
    conn.close()
    if row:
        return int(row[0]) == current_size
    return False

def get_all_local_pkgs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT json_extract(data, '$.local_pkg') FROM games")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows if row[0]]

def remove_game_by_path(file_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data FROM games WHERE json_extract(data, '$.local_pkg') = ?", (file_path,))
    row = c.fetchone()
    icon_path = None
    if row:
        game_data = json.loads(row[0])
        icon_path = game_data.get("local_icon")
        c.execute("DELETE FROM games WHERE json_extract(data, '$.local_pkg') = ?", (file_path,))
        conn.commit()
        logger.info(f"Removed from DB: {file_path}")
    conn.close()
    return icon_path