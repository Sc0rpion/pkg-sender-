"""
Сетевой модуль API.
Включает эндпоинты каталога, системных логов, локализации, Range-запросов и прокси PS5.
"""
import os
import socket
import time
import json
import threading
import urllib.request
import shutil
from urllib.parse import urlparse, parse_qs
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from logger import logger
import config
from config import PORT
from db import get_all_catalog, get_game
import feedback
import scanner

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except: return '127.0.0.1'
    finally: s.close()

class PkgSenderHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Range')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        feedback.add_known_ip(self.client_address[0])
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length).decode('utf-8', errors='ignore')
            try:
                data = json.loads(post_data)
            except:
                data = {"raw_text": post_data}
            logger.info(f"[PS5 Report] {self.path}: {json.dumps(data, ensure_ascii=False)}")
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "success"}')

    def serve_file_with_range(self, file_path, content_type="application/octet-stream"):
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            self.send_error(404, "File not found on disk")
            return

        range_header = self.headers.get('Range')
        if range_header:
            try:
                range_match = range_header.replace('bytes=', '').split('-')
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
                
                if start >= file_size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    return
                end = min(end, file_size - 1)
                chunk_size = end - start + 1
                
                self.send_response(206)
                self.send_header('Content-type', content_type)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(chunk_size))
                self.end_headers()

                with open(file_path, 'rb') as f:
                    f.seek(start)
                    bytes_left = chunk_size
                    while bytes_left > 0:
                        read_size = min(1048576, bytes_left)
                        data = f.read(read_size)
                        if not data: break
                        self.wfile.write(data)
                        bytes_left -= len(data)
            except Exception:
                return
        else:
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()
            try:
                with open(file_path, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile, length=1048576)
            except Exception:
                pass

    def do_GET(self):
        feedback.add_known_ip(self.client_address[0])
        parsed_path = urlparse(self.path)
        base_path = parsed_path.path

        if base_path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(feedback.get_html_page().encode('utf-8'))
            return
            
        elif base_path == '/locales':
            locales_path = os.path.join(os.path.dirname(__file__), 'locales.json')
            try:
                with open(locales_path, 'r', encoding='utf-8') as f:
                    locales_data = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(locales_data.encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Locales file missing: {e}")
            return
            
        elif base_path == '/logs':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            try:
                log_path = 'app.log'
                if not os.path.exists(log_path):
                    log_path = os.path.join(os.path.dirname(__file__), 'app.log')
                if os.path.exists(log_path):
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        output = "".join(lines)
                        self.wfile.write(output.encode('utf-8'))
                else:
                    self.wfile.write(b"Log file not found.")
            except Exception as e:
                self.wfile.write(f"Error reading log file: {e}".encode('utf-8'))
            return

        elif base_path == '/api/known_ips':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(feedback.get_known_ips()).encode('utf-8'))
            return
            
        elif base_path == '/api/ps5_status':
            ip = parse_qs(parsed_path.query).get('ip', [''])[0]
            res_data = {"online": False, "status": {}}
            if ip:
                try:
                    req = urllib.request.Request(f"http://{ip}:12800/api/status")
                    with urllib.request.urlopen(req, timeout=2) as response:
                        res_data["online"] = True
                        res_data["status"] = json.loads(response.read().decode('utf-8'))
                except Exception:
                    pass
                    
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res_data).encode('utf-8'))
            return
            
        elif base_path == '/api/trigger_install':
            ip = parse_qs(parsed_path.query).get('ip', [''])[0]
            game_id = parse_qs(parsed_path.query).get('id', [''])[0]
            res_data = {"status": "error", "message": "Неизвестная ошибка"}

            if not ip:
                res_data["message"] = "IP консоли не указан"
            elif not game_id:
                res_data["message"] = "ID игры не указан"
            else:
                game_data = get_game(game_id)
                if not game_data:
                    res_data["message"] = "Игра не найдена в базе NAS"
                    logger.error(f"[WebUI] Install error: game {game_id} not found in DB.")
                else:
                    nas_ip = get_local_ip()
                    pkg_url = f"http://{nas_ip}:{PORT}/pkg/{game_id}.pkg"
                    icon_url = f"http://{nas_ip}:{PORT}/icon/{game_id}.png"
                    name = game_data["catalog"].get("title", "Unknown")

                    logger.info(f"[WebUI] Install requested for '{name}' to console {ip}")

                    payload = json.dumps({
                        "packages": [pkg_url],
                        "name": name,
                        "icon_url": icon_url
                    }).encode('utf-8')

                    try:
                        req = urllib.request.Request(f"http://{ip}:12800/api/install", data=payload, headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=3) as response:
                            ps5_reply = json.loads(response.read().decode('utf-8'))
                            if ps5_reply.get("status") == "success":
                                res_data = {"status": "success", "message": "Команда успешно передана на консоль"}
                                reply_str = json.dumps(ps5_reply, ensure_ascii=False)
                                logger.info(f"[WebUI] Install command for '{name}' successfully accepted by console {ip}. Reply from PS5: {reply_str}")
                            else:
                                res_data["message"] = f"Консоль вернула ошибку: {ps5_reply}"
                                reply_str = json.dumps(ps5_reply, ensure_ascii=False)
                                logger.warning(f"[WebUI] Console {ip} returned an error during installation of '{name}': {reply_str}")
                    except Exception as e:
                        res_data["message"] = f"Ошибка связи с консолью: {str(e)}"
                        logger.error(f"[WebUI] Connection error with {ip} during installation of '{name}': {e}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res_data).encode('utf-8'))
            return

        elif base_path == '/api/config':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            folder_exists = os.path.exists(config.PKG_FOLDER)
            folder_readable = os.access(config.PKG_FOLDER, os.R_OK) if folder_exists else False
            self.wfile.write(json.dumps({
                "pkg_folder": config.PKG_FOLDER,
                "server_port": config.PORT,
                "folder_exists": folder_exists,
                "folder_readable": folder_readable
            }).encode('utf-8'))
            return

        elif base_path == '/api/rescan':
            scanner.trigger_rescan(reason="Web UI manual rescan button")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "message": "Сканирование папки запущено"
            }).encode('utf-8'))
            return

        elif base_path == '/catalog':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_all_catalog()).encode('utf-8'))
            return
            
        elif base_path.startswith('/icon/'):
            game_id = base_path.split('/')[2]
            if game_id.endswith('.png'): game_id = game_id[:-4]
            
            game_data = get_game(game_id)
            if game_data and game_data.get("local_icon"):
                self.serve_file_with_range(game_data["local_icon"], content_type="image/png")
            else:
                self.send_error(404, "Icon not found")
            return
            
        elif base_path.startswith('/pkg/'):
            game_id = base_path.split('/')[2]
            if game_id.endswith('.pkg'): game_id = game_id[:-4]
            
            game_data = get_game(game_id)
            if game_data and game_data.get("local_pkg"):
                self.serve_file_with_range(game_data["local_pkg"], content_type="application/octet-stream")
            else:
                self.send_error(404, "PKG not found")
            return
                
        else:
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            return

    def do_POST(self):
        parsed_path = urlparse(self.path)
        base_path = parsed_path.path

        if base_path == '/api/config':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                folder = data.get('pkg_folder', '').strip()
                port = int(data.get('server_port', config.PORT))
                if folder:
                    config.save_config(folder, port)
                    scanner.trigger_rescan()
                    res = {"status": "success", "message": "Настройки сохранены, сканирование папки началось"}
                else:
                    res = {"status": "error", "message": "Путь к папке не может быть пустым"}
            except Exception as e:
                res = {"status": "error", "message": str(e)}

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
            return

        elif base_path == '/api/rescan':
            scanner.trigger_rescan()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Сканирование папки запущено"}).encode('utf-8'))
            return

        else:
            self.send_error(404, "Not Found")
            return

    def log_message(self, format, *args):
        if '"GET /logs' not in format%args and '"GET /api/ps5_status' not in format%args and '"GET /api/known_ips' not in format%args:
            logger.debug(f"{self.address_string()} - {format%args}")

def udp_broadcaster(shutdown_event):
    real_ip = get_local_ip()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = f"PKGSENDER-PC {real_ip}:{PORT}".encode('utf-8')
    logger.info(f"Started UDP Broadcast at {real_ip}:{PORT}")
    
    while not shutdown_event.is_set():
        try:
            sock.sendto(message, ('255.255.255.255', 12802))
        except Exception as e:
            pass
        shutdown_event.wait(3)

def start_http_server(shutdown_event):
    server = ThreadingHTTPServer(('0.0.0.0', PORT), PkgSenderHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.info(f"HTTP Server running on port {PORT}. UI: http://{get_local_ip()}:{PORT}")
    
    shutdown_event.wait()
    logger.info("Shutting down HTTP Server...")
    
    server.shutdown()
    server.server_close()
    server_thread.join()