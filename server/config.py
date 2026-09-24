"""
Модуль загрузки и сохранения конфигурации.
"""
import json
import os
from logger import logger

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def get_config():
    """
    Парсит config.json. Если файл отсутствует или поврежден, 
    возвращает безопасные настройки по умолчанию.
    """
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            folder = config.get("pkg_folder", "/volume1/downloads")
            port = int(config.get("server_port", 9898))
            return folder, port
    except Exception as e:
        logger.error(f"Failed to read config, using defaults. Error: {e}")
        return "/volume1/downloads", 9898

def save_config(folder: str, port: int = 9898):
    """
    Сохраняет параметры в config.json.
    """
    global PKG_FOLDER, PORT
    try:
        data = {
            "pkg_folder": folder.strip(),
            "server_port": int(port)
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        PKG_FOLDER = folder.strip()
        PORT = int(port)
        return True
    except Exception as e:
        logger.error(f"Failed to write config: {e}")
        return False

PKG_FOLDER, PORT = get_config()
