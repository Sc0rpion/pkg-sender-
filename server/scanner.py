"""
Служба мониторинга файловой системы (Watchdog / Events).
Отслеживает изменения только для .pkg файлов, логирует точную причину запуска сканирования
и предотвращает холостые сканирования дисков, если файловая система не менялась.
"""
import os
import sys

# Ensure bundled libraries (e.g. watchdog) in server/lib are available
_current_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_current_dir, 'lib')
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

import time
import threading
from logger import logger
import config
from db import game_exists_and_unchanged, save_game, get_all_local_pkgs, remove_game_by_path
from parser import extract_pkg_meta

_scan_lock = threading.Lock()

def cleanup_deleted_files():
    """
    Сборщик мусора. Сверяет записи БД с реальным наличием файлов на диске.
    Удаляет сиротевшие записи и привязанные к ним PNG обложки.
    """
    pkg_folder = config.PKG_FOLDER
    if not os.path.exists(pkg_folder):
        logger.warning(f"Scan folder does not exist: {pkg_folder}. Skipping cleanup to protect database.")
        return

    for pkg_path in get_all_local_pkgs():
        if not pkg_path.startswith(pkg_folder):
            continue
        if not os.path.exists(pkg_path):
            logger.info(f"PKG removed or renamed, clearing DB entry for: {pkg_path}")
            icon_path = remove_game_by_path(pkg_path)
            if icon_path and os.path.exists(icon_path):
                try:
                    os.remove(icon_path)
                    logger.info(f"Deleted associated icon: {icon_path}")
                except Exception as e:
                    logger.error(f"Failed to delete icon {icon_path}: {e}")

def wait_for_file_ready(file_path, shutdown_event=None, wait_time=2):
    """Ждет завершения копирования файла по сети или торрента."""
    try:
        initial_size = os.path.getsize(file_path)
        if shutdown_event:
            shutdown_event.wait(wait_time)
            if shutdown_event.is_set():
                return False
        else:
            time.sleep(wait_time)
        return initial_size == os.path.getsize(file_path)
    except Exception:
        return False

def process_new_file(file_path, shutdown_event=None, reason="Filesystem event"):
    if not file_path.lower().endswith('.pkg'):
        return

    try:
        current_size = os.path.getsize(file_path)
    except Exception as e:
        logger.warning(f"Cannot read file size (Permission Denied?): {file_path} - {e}")
        return

    if game_exists_and_unchanged(file_path, current_size):
        return

    logger.info(f"[{reason}] New or modified PKG detected, verifying: {file_path}")
    while not wait_for_file_ready(file_path, shutdown_event):
        if shutdown_event and shutdown_event.is_set():
            return

    try:
        game_data = extract_pkg_meta(file_path)
        if game_data:
            save_game(game_data["catalog"]["id"], game_data)
            logger.info(f"Successfully indexed game: {game_data.get('catalog', {}).get('title')} ({game_data.get('catalog', {}).get('titleId')}) from {file_path}")
        else:
            logger.warning(f"Failed to extract PKG metadata: {file_path}")
    except Exception as e:
        logger.error(f"Exception during PKG parsing for {file_path}: {e}", exc_info=True)

def full_scan(shutdown_event=None, reason="Startup"):
    if not _scan_lock.acquire(blocking=False):
        logger.info(f"Scan request skipped (reason: '{reason}'), another scan is already in progress.")
        return

    try:
        pkg_folder = config.PKG_FOLDER
        logger.info(f"Starting directory scan: {pkg_folder} (Reason: {reason})")

        if not os.path.exists(pkg_folder):
            logger.error(f"Scan folder DOES NOT EXIST: '{pkg_folder}'. Please verify path in config.json or DSM wizard.")
            return

        # Проверка прав чтения для сервисного аккаунта
        if not os.access(pkg_folder, os.R_OK):
            logger.error(f"CRITICAL: Current process (user: {os.getuid() if hasattr(os, 'getuid') else 'unknown'}) has NO READ PERMISSION on '{pkg_folder}'! In DSM -> Control Panel -> Shared Folder -> Edit '{os.path.basename(pkg_folder)}' -> Permissions -> System internal user -> Grant Read/Write to 'pkg-sender'.")
            return

        cleanup_deleted_files()

        def on_walk_error(err):
            logger.error(f"Permission or I/O error accessing subfolder '{err.filename}': {err}")

        found_count = 0
        folders_count = 0

        for root, dirs, files in os.walk(pkg_folder, onerror=on_walk_error, followlinks=True):
            folders_count += 1
            if shutdown_event and shutdown_event.is_set():
                break

            for file in files:
                if shutdown_event and shutdown_event.is_set():
                    break
                if file.lower().endswith('.pkg'):
                    found_count += 1
                    file_path = os.path.join(root, file)
                    process_new_file(file_path, shutdown_event, reason=f"Directory scan: {reason}")

        logger.info(f"Directory scan finished: {pkg_folder} (Scanned {folders_count} folder(s), found {found_count} .pkg file(s))")

    except Exception as e:
        logger.error(f"Fatal error during full_scan: {e}", exc_info=True)
    finally:
        _scan_lock.release()

def trigger_rescan(reason="User request"):
    """Запуск сканирования по требованию."""
    t = threading.Thread(target=full_scan, args=(None, reason), daemon=True)
    t.start()

def start_scanner(shutdown_event):
    # 1. Первичное сканирование при старте сервера
    full_scan(shutdown_event, reason="Server startup initial catalog check")

    # 2. Запуск файлового мониторинга Watchdog
    watchdog_running = False
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class PkgHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory and event.src_path.lower().endswith('.pkg'):
                    process_new_file(event.src_path, shutdown_event, reason="Watchdog File Created")

            def on_modified(self, event):
                if not event.is_directory and event.src_path.lower().endswith('.pkg'):
                    process_new_file(event.src_path, shutdown_event, reason="Watchdog File Modified")

            def on_moved(self, event):
                if not event.is_directory:
                    if event.src_path.lower().endswith('.pkg'):
                        cleanup_deleted_files()
                    if event.dest_path.lower().endswith('.pkg'):
                        process_new_file(event.dest_path, shutdown_event, reason="Watchdog File Moved/Renamed")

            def on_deleted(self, event):
                if not event.is_directory and event.src_path.lower().endswith('.pkg'):
                    logger.info(f"[Watchdog File Deleted] PKG removed: {event.src_path}")
                    cleanup_deleted_files()

        observer = Observer()
        if os.path.exists(config.PKG_FOLDER):
            observer.schedule(PkgHandler(), path=config.PKG_FOLDER, recursive=True)
            observer.start()
            watchdog_running = True
            logger.info(f"Watchdog active on {config.PKG_FOLDER}. Listening for PKG filesystem events (ignoring non-pkg files).")

        # При активном Watchdog полный опрос диска нужен лишь раз в 1 час для профилактической синхронизации
        # (или если события по сети не отловились inotify)
        sync_interval = 3600

        while not shutdown_event.is_set():
            shutdown_event.wait(sync_interval)
            if not shutdown_event.is_set():
                full_scan(shutdown_event, reason="Periodic background catalog sync (1h interval)")

        if observer.is_alive():
            observer.stop()
            observer.join()

    except ImportError as e:
        logger.warning(f"Watchdog not available ({e}). Falling back to 10-minute polling.")
        while not shutdown_event.is_set():
            shutdown_event.wait(600)
            if not shutdown_event.is_set():
                full_scan(shutdown_event, reason="Periodic polling (Watchdog unavailable, 10m interval)")
    except Exception as e:
        logger.error(f"Watchdog failed on {config.PKG_FOLDER}: {e}. Falling back to 10-minute polling.")
        while not shutdown_event.is_set():
            shutdown_event.wait(600)
            if not shutdown_event.is_set():
                full_scan(shutdown_event, reason="Periodic polling fallback after Watchdog failure (10m interval)")
