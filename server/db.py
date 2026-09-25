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

ROLE_WEIGHT = {"GAME": 1, "PATCH": 2, "DLC": 3}

def sort_catalog_list(catalog_items):
    """
    Группирует и сортирует список каталога:
    Каждая игра объединяется по Title ID (например, PPSA29180),
    внутри группы строго по порядку: Game (базовая игра) -> Patch (обновления) -> DLC -> Ошибки.
    Группы сортируются: PS5 -> PS4 -> по алфавиту названия.
    """
    grouped = {}
    for item in catalog_items:
        key = item.get("familyKey") or item.get("titleId") or "UNKNOWN"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(item)

    for group in grouped.values():
        def item_sort_key(it):
            is_err = 1 if it.get("error") else 0
            role_w = ROLE_WEIGHT.get(str(it.get("role", "")).upper(), 4)
            ver = str(it.get("version", "0.00")).lower()
            return (is_err, role_w, ver)
        group.sort(key=item_sort_key)

    group_arr = list(grouped.values())
    def group_sort_key(grp):
        plat = 1 if grp[0].get("platform") == "PS5" else 0
        title = (grp[0].get("title") or "").lower()
        return (-plat, title)

    group_arr.sort(key=group_sort_key)
    return [item for group in group_arr for item in group]

def get_all_catalog():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data FROM games")
    rows = c.fetchall()
    conn.close()
    raw_catalog = [json.loads(row[0])["catalog"] for row in rows]
    return sort_catalog_list(raw_catalog)


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