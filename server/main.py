"""
Главный контроллер жизненного цикла приложения.
Инициализирует базу данных, запускает рабочие потоки (Сканер, HTTP, UDP) 
и перехватывает сигналы операционной системы для штатного завершения работы 
(Graceful Shutdown), предотвращая обрыв скачивания или повреждение БД.
"""
import os
import sys

# Ensure bundled libraries (e.g. watchdog) in server/lib are available
_current_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_current_dir, 'lib')
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

import threading
import signal
import sys
from logger import logger
from db import init_db
from scanner import start_scanner
from server import start_http_server, udp_broadcaster

# Глобальный флаг синхронизации завершения потоков
shutdown_event = threading.Event()

def handle_exit_signal(signum, frame):
    """
    Обработчик сигналов SIGTERM/SIGINT.
    Вызывается, когда пользователь нажимает "Остановить" в DSM.
    """
    logger.info(f"Received exit signal ({signum}). Initiating graceful shutdown...")
    shutdown_event.set()

if __name__ == '__main__':
    logger.info("=== Starting Pkg Sender Backend ===")
    
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)
    
    # Инициализация хранилища
    init_db()
    
    # Запуск службы сканирования и сборки мусора
    scanner_thread = threading.Thread(target=start_scanner, args=(shutdown_event,))
    scanner_thread.start()
    
    # Запуск службы автообнаружения (UDP)
    udp_thread = threading.Thread(target=udp_broadcaster, args=(shutdown_event,))
    udp_thread.start()
    
    # Запуск сетевого API. Эта функция блокирует выполнение, 
    # пока не будет вызван shutdown_event.set()
    start_http_server(shutdown_event)
    
    # Гарантированное завершение фоновых задач
    scanner_thread.join()
    udp_thread.join()
    
    logger.info("=== Application safely terminated ===")
    sys.exit(0)