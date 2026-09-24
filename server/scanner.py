"""
Служба мониторинга файловой системы (Watchdog / Polling).
"""
import os
import time
import threading
from logger import logger
import config
from db import game_exists_and_unchanged, save_game, get_all_local_pkgs, remove_game_by_path
from parser import extract_pkg_meta

_scan_lock = threading.Lock()

def cleanup_deleted_files():
    """
    Сборщик мусора. Сверяет записи БД с реальным наличием файлов.
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

def wait_for_file_ready(file_path, shutdown_event=None, wait_time=3):
    """Ждет завершения копирования файла по сети."""
    try:
        initial_size = os.path.getsize(file_path)
        if shutdown_event:
            shutdown_event.wait(wait_time)
            if shutdown_event.is_set(): return False
        else:
            time.sleep(wait_time)
        return initial_size == os.path.getsize(file_path)
    except Exception:
        return False

def process_new_file(file_path, shutdown_event=None):
    if not file_path.endswith('.pkg'): return
    try:
        current_size = os.path.getsize(file_path)
    except Exception:
        return
        
    if game_exists_and_unchanged(file_path, current_size): return
    
    logger.info(f"New or modified PKG detected, waiting for transfer: {file_path}")
    while not wait_for_file_ready(file_path, shutdown_event):
        if shutdown_event and shutdown_event.is_set(): return
        
    game_data = extract_pkg_meta(file_path)
    if game_data:
        save_game(game_data["catalog"]["id"], game_data)

def full_scan(shutdown_event=None):
    if not _scan_lock.acquire(blocking=False):
        logger.info("Scan is already in progress, skipping duplicate call.")
        return

    try:
        pkg_folder = config.PKG_FOLDER
        if not os.path.exists(pkg_folder):
            logger.warning(f"Scan folder does not exist: {pkg_folder}")
            return
        cleanup_deleted_files()
            
        logger.info(f"Starting directory scan: {pkg_folder}")
        for root, dirs, files in os.walk(pkg_folder):
            if shutdown_event and shutdown_event.is_set(): break
            for file in files:
                if shutdown_event and shutdown_event.is_set(): break
                if file.endswith('.pkg'):
                    process_new_file(os.path.join(root, file), shutdown_event)
        logger.info(f"Directory scan finished: {pkg_folder}")
    finally:
        _scan_lock.release()

def trigger_rescan():
    """Запуск сканирования в отдельном потоке."""
    t = threading.Thread(target=full_scan, daemon=True)
    t.start()

def start_scanner(shutdown_event):
    full_scan(shutdown_event)
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class PkgHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    process_new_file(event.src_path, shutdown_event)

            def on_modified(self, event):
                if not event.is_directory: 
                    process_new_file(event.src_path, shutdown_event)
            
            def on_moved(self, event):
                if not event.is_directory:
                    cleanup_deleted_files()
                    process_new_file(event.dest_path, shutdown_event)
            
            def on_deleted(self, event):
                if not event.is_directory and event.src_path.endswith('.pkg'):
                    cleanup_deleted_files()
                
        observer = Observer()
        if os.path.exists(config.PKG_FOLDER):
            observer.schedule(PkgHandler(), path=config.PKG_FOLDER, recursive=True)
            observer.start()
            logger.info(f"Watchdog started on {config.PKG_FOLDER}. Listening for filesystem events.")
        
        while not shutdown_event.is_set():
            shutdown_event.wait(300)
            if not shutdown_event.is_set():
                full_scan(shutdown_event)
                
        if observer.is_alive():
            observer.stop()
            observer.join()
            
    except ImportError:
        logger.warning("Watchdog not found. Falling back to 5-minute polling.")
        while not shutdown_event.is_set():
            shutdown_event.wait(300)
            if not shutdown_event.is_set():
                full_scan(shutdown_event)
