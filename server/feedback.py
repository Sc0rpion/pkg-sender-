"""
Модуль сбора обратной связи, трекинга IP-адресов и генерации Web-интерфейса.
"""
import json
from datetime import datetime
from logger import logger

_known_ips = set()

def add_known_ip(ip):
    if ip and ip not in ("127.0.0.1", "::1", "localhost"):
        _known_ips.add(ip)

def get_known_ips():
    return list(_known_ips)

def get_html_page():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>PKGri NAS</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: #e0e0e0; margin: 0; padding: 20px; line-height: 1.6; }
        h1, h2, h3 { color: #ffffff; margin-top: 0; }
        .container { max-width: 1100px; margin: 0 auto; }
        
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; flex-wrap: wrap; gap: 15px; }
        .logo-container { display: flex; align-items: center; gap: 15px; }
        .lang-select { background: #1e1e1e; border: 1px solid #444; color: #fff; padding: 8px 12px; border-radius: 6px; font-size: 0.95em; cursor: pointer; }
        .lang-select:focus { outline: none; border-color: #64b5f6; }

        .card { background: #1e1e1e; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #333; }
        details.card { padding: 15px 25px; cursor: pointer; }
        details.card[open] { cursor: default; }
        summary { font-size: 1.3em; font-weight: bold; color: #fff; outline: none; margin: 10px 0; cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center;}
        summary::-webkit-details-marker { display: none; }
        summary::after { content: "▼"; font-size: 0.8em; color: #888; transition: transform 0.2s;}
        details[open] summary::after { transform: rotate(180deg); }
        
        .badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 0.8em; background: #333; color: #fff; margin-bottom: 10px; font-weight: bold; text-transform: uppercase; }
        .bg-online { background: #2e7d32; }
        .bg-offline { background: #c62828; }
        .bg-error { background: #b71c1c; }
        
        .badge-ps5 { background: #1a1a1a; border: 1px solid #ffffff; color: #ffffff; }
        .badge-ps4 { background: #003791; border: 1px solid #0055d4; color: #ffffff; }
        .badge-pkg { background: #424242; border: 1px solid #666; }
        .badge-game { background: #2e7d32; border: 1px solid #43a047; }
        .badge-patch { background: #ef6c00; border: 1px solid #f57c00; }
        .badge-dlc { background: #6a1b9a; border: 1px solid #8e24aa; }
        .badge-unknown { background: #546e7a; border: 1px solid #78909c; }
        
        input[type="text"] { background: #121212; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 6px; font-size: 1em; }
        input[type="text"]:focus { outline: none; border-color: #64b5f6; }
        
        .progress-bg { background: #333; border-radius: 8px; width: 100%; position: relative; }
        .progress-bar { background: #1976d2; height: 100%; width: 0%; transition: width 0.5s; border-radius: 8px; }
        .progress-text { position: absolute; top: 0; left: 0; width: 100%; text-align: center; color: #fff; font-weight: bold; text-shadow: 1px 1px 2px #000; }
        
        .filters-container { background: #252525; padding: 12px 20px; border-radius: 8px; display: flex; gap: 20px; align-items: center; flex-wrap: wrap; margin-top: 15px; border: 1px solid #333;}
        .filter-group { display: flex; gap: 10px; align-items: center; font-size: 0.9em; }
        .filter-group label { display: flex; align-items: center; gap: 5px; cursor: pointer; color: #ccc; }
        .filter-group input[type="checkbox"] { cursor: pointer; accent-color: #64b5f6; width: 16px; height: 16px;}
        
        .games-list { display: flex; flex-direction: column; gap: 12px; margin-top: 15px; }
        .game-row { background: #121212; border: 1px solid #333; border-radius: 8px; padding: 12px 15px; display: flex; gap: 20px; align-items: center; transition: border-color 0.2s; }
        .game-row:hover { border-color: #555; }
        .game-icon { width: 64px; height: 64px; border-radius: 6px; background: #222; object-fit: cover; flex-shrink: 0; border: 1px solid #444; }
        .game-info { flex-grow: 1; overflow: hidden; display: flex; flex-direction: column; justify-content: center;}
        .game-title { font-weight: bold; font-size: 1.1em; margin: 0 0 5px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #fff; }
        .game-meta { font-size: 0.85em; color: #aaa; margin: 2px 0; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;}
        
        .file-line { display: flex; align-items: center; gap: 10px; margin-top: 5px; }
        .game-file { font-size: 0.75em; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: help; border-bottom: 1px dotted #555; }
        .btn-copy { background: #333; color: #ccc; border: none; padding: 2px 6px; border-radius: 4px; cursor: pointer; font-size: 0.8em; transition: background 0.2s, color 0.2s; }
        .btn-copy:hover { background: #444; color: #fff; }
        
        .game-actions { flex-shrink: 0; }
        .btn-install { background: #1976d2; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.9em; transition: background 0.2s, transform 0.1s; }
        .btn-install:hover { background: #1565c0; }
        .btn-install:active { transform: scale(0.95); }
        .btn-install:disabled { background: #444; cursor: not-allowed; color: #888; }
        
        #toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px; }
        .toast { padding: 15px 25px; border-radius: 8px; color: #fff; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.5); opacity: 0; transform: translateX(100%); transition: opacity 0.3s, transform 0.3s; }
        .toast.show { opacity: 1; transform: translateX(0); }
        .toast-error { background: #d32f2f; border-left: 5px solid #b71c1c; }
        .toast-success { background: #388e3c; border-left: 5px solid #1b5e20; }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <div class="logo-container">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="46" height="46" style="filter: drop-shadow(0 4px 6px rgba(0,0,0,0.5)); border-radius: 10px;">
                  <defs>
                    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#2a2a2a" />
                      <stop offset="100%" stop-color="#121212" />
                    </linearGradient>
                    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                      <feGaussianBlur stdDeviation="8" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>
                  <rect width="256" height="256" rx="56" fill="url(#bg)" />
                  <rect width="252" height="252" x="2" y="2" rx="54" fill="none" stroke="#444" stroke-width="2" />
                  <g filter="url(#glow)">
                    <polygon points="128,70 190,105 128,140 66,105" fill="#1e88e5" />
                    <polygon points="66,105 128,140 128,210 66,175" fill="#1565c0" />
                    <polygon points="128,140 190,105 190,175 128,210" fill="#0d47a1" />
                    <polyline points="128,140 128,210" fill="none" stroke="#0a3275" stroke-width="4" />
                    <polyline points="66,105 128,140 190,105" fill="none" stroke="#64b5f6" stroke-width="2" />
                    <path d="M 85 145 C 75 145, 75 160, 85 160 C 95 160, 95 145, 85 145 Z M 105 155 C 95 155, 95 170, 105 170 C 115 170, 115 155, 105 155 Z" fill="#ffffff" opacity="0.8" transform="rotate(30 95 157)" />
                    <path d="M 128 20 L 128 85 M 105 60 L 128 85 L 151 60" fill="none" stroke="#ffffff" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" />
                  </g>
                </svg>
                <h1 style="margin: 0;">Pkg Sender NAS</h1>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <button onclick="openSettingsModal()" style="background: #263238; border: 1px solid #37474f; color: #eceff1; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.9em; display: inline-flex; align-items: center; gap: 6px; font-weight: 500;">
                    ⚙️ <span data-i18n="btn_settings">Настройки</span>
                </button>
                <select id="langSelect" class="lang-select" onchange="changeLanguage(this.value)">
                    <option value="ru">🇷🇺 Русский</option>
                    <option value="en">🇬🇧 English</option>
                    <option value="fr">🇫🇷 Français</option>
                    <option value="de">🇩🇪 Deutsch</option>
                    <option value="es">🇪🇸 Español</option>
                    <option value="ja">🇯🇵 日本語</option>
                </select>
            </div>
        </div>
        
        <!-- БЛОК 1: Статус Консоли -->
        <div class="card" style="padding: 15px 25px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <strong data-i18n="c1_title" style="font-size: 1.1em; margin-right: 10px;">📺 Консоль PS5:</strong>
                    <input type="text" id="ps5_ip" list="ip_list" placeholder="192.168.0.103" style="width: 180px; padding: 6px 10px;" oninput="onIpManualInput(this.value)">
                    <datalist id="ip_list"></datalist>
                    <span id="conn_status" class="badge bg-offline" style="margin:0;" data-i18n="status_wait">Ожидание...</span>
                </div>
                <div id="ps5_dashboard" style="display: none; font-size: 0.9em; align-items: center; gap: 15px;">
                    <div><span style="color:#888;" data-i18n="st_state">Статус:</span> <strong id="st_busy" style="color: #81c784;">...</strong></div>
                </div>
            </div>
            <div id="progress_container" style="display: none; margin-top: 15px; border-top: 1px solid #333; padding-top: 15px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #aaa;">
                    <span id="st_downloaded">0 MB</span>
                    <span id="st_total">0 MB</span>
                </div>
                <div class="progress-bg" style="margin-top: 5px; height: 16px;">
                    <div class="progress-bar" id="st_progress_bar"></div>
                    <div class="progress-text" id="st_progress_txt" style="line-height: 16px; font-size: 0.8em;">0%</div>
                </div>
            </div>
        </div>
        
        <!-- БЛОК 2: Доступные игры -->
        <details class="card" open>
            <summary>
                <div data-i18n="c3_title">📁 Доступные игры (База NAS)</div>
                <span id="catalog_count" class="badge bg-info" style="margin:0; font-size: 0.7em;">Загрузка...</span>
            </summary>
            
            <div class="filters-container">
                <input type="text" id="searchInput" data-i18n-ph="f_search" placeholder="Поиск (Название, TitleID)..." style="flex-grow: 1;" oninput="renderCatalog()">
                <div class="filter-group">
                    <strong data-i18n="f_platform">Платформа:</strong>
                    <label><input type="checkbox" id="chk_ps5" checked onchange="renderCatalog()"> PS5</label>
                    <label><input type="checkbox" id="chk_ps4" checked onchange="renderCatalog()"> PS4</label>
                </div>
                <div class="filter-group">
                    <strong data-i18n="f_type">Тип:</strong>
                    <label><input type="checkbox" id="chk_game" checked onchange="renderCatalog()"> Game</label>
                    <label><input type="checkbox" id="chk_patch" checked onchange="renderCatalog()"> Patch</label>
                    <label><input type="checkbox" id="chk_dlc" checked onchange="renderCatalog()"> DLC</label>
                </div>
                <div class="filter-group" style="border-left: 1px solid #444; padding-left: 15px;">
                    <label style="color: #ef5350;"><input type="checkbox" id="chk_err" onchange="renderCatalog()"> <span data-i18n="f_err">Ошибки</span></label>
                </div>
            </div>
            
            <div id="games_container" class="games-list"></div>
        </details>
        
        <!-- ПОДВАЛ -->
        <footer style="text-align: center; margin-top: 20px; padding-bottom: 20px; color: #666; font-size: 0.9em;">
            <div style="margin-bottom: 5px; color: #888;">
                Created by Sc0rpion (Assisted by Gemini) • 
                <a href="https://github.com/Sc0rpion" target="_blank" style="color: #64b5f6; text-decoration: none;">GitHub</a>
            </div>
            <div>
                Based on the original project API: 
                <a href="https://github.com/Loopayeh/pkg-sender" target="_blank" style="color: #64b5f6; text-decoration: none;">PKGri</a>
            </div>
            <div style="margin-top: 10px;">
                <a href="/logs" target="_blank" style="color: #aaa; text-decoration: underline;" data-i18n="footer_logs">Системный журнал (app.log)</a>
            </div>
        </footer>
    </div>
    
    <div id="toast-container"></div>
    
    <!-- Модальное окно настроек -->
    <div id="settings_modal" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.7); z-index: 10000; align-items: center; justify-content: center; backdrop-filter: blur(3px);">
        <div style="background: #1e1e1e; border: 1px solid #444; border-radius: 12px; width: 92%; max-width: 540px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); color: #fff;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border-bottom: 1px solid #333; padding-bottom: 12px;">
                <h3 style="margin: 0; font-size: 1.2em; display: flex; align-items: center; gap: 8px;">⚙️ <span data-i18n="modal_settings_title">Настройки сервера</span></h3>
                <button onclick="closeSettingsModal()" style="background: transparent; border: none; color: #aaa; font-size: 1.6em; cursor: pointer; line-height: 1;">&times;</button>
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="display: block; font-size: 0.9em; color: #bbb; margin-bottom: 6px;" data-i18n="lbl_pkg_folder">Путь к папке с файлами .pkg на Synology:</label>
                <input type="text" id="cfg_pkg_folder" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 6px; border: 1px solid #555; background: #121212; color: #fff; font-family: monospace; font-size: 0.95em;" placeholder="/volume1/downloads">
                <div style="margin-top: 8px; font-size: 0.8em; color: #888;">
                    <span data-i18n="lbl_suggestions">Быстрый выбор:</span>
                    <a href="javascript:void(0)" onclick="setFolder('/volume1/downloads')" style="color: #64b5f6; margin-left: 6px;">/volume1/downloads</a>
                    <a href="javascript:void(0)" onclick="setFolder('/volume1/PS_Games')" style="color: #64b5f6; margin-left: 6px;">/volume1/PS_Games</a>
                    <a href="javascript:void(0)" onclick="setFolder('/volume2/downloads')" style="color: #64b5f6; margin-left: 6px;">/volume2/downloads</a>
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <label style="display: block; font-size: 0.9em; color: #bbb; margin-bottom: 6px;" data-i18n="lbl_server_port">Сетевой порт веб-сервера:</label>
                <input type="number" id="cfg_server_port" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 6px; border: 1px solid #555; background: #121212; color: #fff; font-family: monospace; font-size: 0.95em;" value="9898">
                <div style="margin-top: 5px; font-size: 0.75em; color: #777;" data-i18n="lbl_port_hint">По умолчанию: 9898 (при смене порта требуется перезапуск службы).</div>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid #333; padding-top: 16px;">
                <button onclick="rescanOnly()" style="background: #37474f; border: 1px solid #455a64; color: #fff; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9em;" data-i18n="btn_rescan_now">🔄 Пересканировать</button>
                <button onclick="saveServerConfig()" style="background: #1976d2; border: 1px solid #1565c0; color: #fff; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.9em;" data-i18n="btn_save_rescan">💾 Сохранить</button>
            </div>
        </div>
    </div>
    
    <script>
        let translations = {};
        let currentLang = localStorage.getItem('pkg_sender_lang') || 'ru';
        document.getElementById('langSelect').value = currentLang;
        
        window.allGames = [];

        // Управление историей IP адресов в localStorage
        let ipHistory = JSON.parse(localStorage.getItem('pkg_sender_ip_history') || '[]');
        let ipInput = document.getElementById('ps5_ip');
        
        // Автоподстановка значения IP при старте
        let lastIp = localStorage.getItem('pkg_sender_last_ip') || (ipHistory.length > 0 ? ipHistory[0] : '');
        if (lastIp) {
            ipInput.value = lastIp;
        }

        function saveSuccessfulIp(ip) {
            if (!ip) return;
            localStorage.setItem('pkg_sender_last_ip', ip);
            if (!ipHistory.includes(ip)) {
                ipHistory.unshift(ip);
                if (ipHistory.length > 10) ipHistory.pop();
                localStorage.setItem('pkg_sender_ip_history', JSON.stringify(ipHistory));
            }
            updateIpDatalist();
        }

        function onIpManualInput(val) {
            localStorage.setItem('pkg_sender_last_ip', val);
            pollPS5Status(); // Проверяем статус сразу при ручном вводе
        }

        async function updateIpDatalist() {
            let dl = document.getElementById('ip_list');
            dl.innerHTML = '';
            
            let netIps = [];
            try {
                let res = await fetch('/api/known_ips');
                netIps = await res.json();
            } catch(e) {}

            let combined = [...new Set([...ipHistory, ...netIps])];
            combined.forEach(ip => {
                let opt = document.createElement('option');
                opt.value = ip;
                dl.appendChild(opt);
            });
        }

        async function loadTranslations() {
            try {
                let res = await fetch('/locales');
                translations = await res.json();
                changeLanguage(currentLang);
            } catch(e) {
                console.error("Failed to load locales.json", e);
            }
        }

        function changeLanguage(lang) {
            currentLang = lang;
            localStorage.setItem('pkg_sender_lang', lang);
            let t = (translations[lang]) ? translations[lang] : (translations['en'] || {});
            
            document.querySelectorAll('[data-i18n]').forEach(el => {
                let key = el.getAttribute('data-i18n');
                if (t[key]) el.innerText = t[key];
            });
            document.querySelectorAll('[data-i18n-ph]').forEach(el => {
                let key = el.getAttribute('data-i18n-ph');
                if (t[key]) el.placeholder = t[key];
            });
            renderCatalog();
        }

        function formatBytes(bytes) {
            if (!bytes || bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function showToast(message, isError = false) {
            let container = document.getElementById('toast-container');
            let toast = document.createElement('div');
            toast.className = 'toast ' + (isError ? 'toast-error' : 'toast-success');
            toast.innerText = message;
            container.appendChild(toast);
            setTimeout(() => { toast.classList.add('show'); }, 10);
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => { toast.remove(); }, 300);
            }, 3000);
        }

        function copyDirectLink(gameId) {
            let t = translations[currentLang] || translations['en'] || {};
            let directUrl = window.location.origin + '/pkg/' + gameId + '.pkg';
            
            let tempInput = document.createElement("input");
            tempInput.style.position = "absolute";
            tempInput.style.left = "-9999px";
            tempInput.value = directUrl;
            document.body.appendChild(tempInput);
            tempInput.select();
            
            try {
                let success = document.execCommand("copy");
                document.body.removeChild(tempInput);
                if (success) {
                    showToast(t.toast_copied || "Скопирована прямая ссылка на файл", false);
                } else {
                    showToast("Не удалось скопировать ссылку", true);
                }
            } catch (err) {
                document.body.removeChild(tempInput);
                showToast("Ошибка копирования", true);
            }
        }

        async function triggerInstall(gameId) {
            let t = translations[currentLang] || translations['en'] || {};
            let ip = ipInput.value;
            if (!ip) {
                showToast(t.toast_no_ip || "Specify IP", true);
                window.scrollTo({ top: 0, behavior: 'smooth' });
                return;
            }
            try {
                let res = await fetch(`/api/trigger_install?ip=${ip}&id=${gameId}`);
                let data = await res.json();
                if (data.status === 'success') {
                    showToast(t.toast_success || "Success", false);
                } else {
                    showToast(data.message, true);
                }
            } catch (e) {
                showToast(t.err_server || "Error", true);
            }
        }

        function getPlatformClass(platform) {
            if (platform === 'PS5') return 'badge-ps5';
            if (platform === 'PS4') return 'badge-ps4';
            return 'badge-unknown';
        }
        
        function getRoleClass(role) {
            let r = role.toUpperCase();
            if (r === 'GAME') return 'badge-game';
            if (r === 'PATCH') return 'badge-patch';
            if (r === 'DLC') return 'badge-dlc';
            return 'badge-unknown';
        }

        async function fetchCatalog() {
            try {
                let res = await fetch('/catalog');
                window.allGames = await res.json();
                renderCatalog();
            } catch(e) {
                document.getElementById('catalog_count').innerText = "Error";
            }
        }

        function renderCatalog() {
            let t = translations[currentLang] || translations['en'] || {};
            let container = document.getElementById('games_container');
            
            let searchTerm = document.getElementById('searchInput').value.toLowerCase();
            let showPS5 = document.getElementById('chk_ps5').checked;
            let showPS4 = document.getElementById('chk_ps4').checked;
            let showGame = document.getElementById('chk_game').checked;
            let showPatch = document.getElementById('chk_patch').checked;
            let showDLC = document.getElementById('chk_dlc').checked;
            let showErr = document.getElementById('chk_err').checked;
            
            let filteredGames = window.allGames.filter(g => {
                let matchesSearch = g.title.toLowerCase().includes(searchTerm) || g.titleId.toLowerCase().includes(searchTerm);
                if (!matchesSearch) return false;
                
                if (g.error) {
                    return showErr;
                }
                
                if (g.platform === 'PS5' && !showPS5) return false;
                if (g.platform === 'PS4' && !showPS4) return false;
                
                let r = g.role.toUpperCase();
                if (r === 'GAME' && !showGame) return false;
                if (r === 'PATCH' && !showPatch) return false;
                if (r === 'DLC' && !showDLC) return false;
                
                return true;
            });
            
            let grouped = {};
            filteredGames.forEach(g => {
                if (!grouped[g.titleId]) grouped[g.titleId] = [];
                grouped[g.titleId].push(g);
            });

            const roleWeight = { 'GAME': 1, 'PATCH': 2, 'DLC': 3 };
            
            Object.values(grouped).forEach(group => {
                group.sort((a, b) => {
                    if (a.error && !b.error) return 1;
                    if (!a.error && b.error) return -1;
                    let wA = roleWeight[a.role.toUpperCase()] || 4;
                    let wB = roleWeight[b.role.toUpperCase()] || 4;
                    return wA - wB;
                });
            });

            let groupArr = Object.values(grouped);
            groupArr.sort((grpA, grpB) => {
                let platA = grpA[0].platform === 'PS5' ? 1 : 0;
                let platB = grpB[0].platform === 'PS5' ? 1 : 0;
                if (platA !== platB) return platB - platA; 
                return grpA[0].title.localeCompare(grpB[0].title); 
            });

            let sortedGames = groupArr.flat();

            document.getElementById('catalog_count').innerText = (t.files_count || "Files: ") + sortedGames.length;
            container.innerHTML = '';
            
            if (sortedGames.length === 0) {
                container.innerHTML = `<div style="text-align: center; padding: 20px; color: #666;">${t.no_games || "Empty"}</div>`;
                return;
            }
            
            sortedGames.forEach(game => {
                let fallbackSvg = "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80'%3E%3Crect width='80' height='80' fill='%23222'/%3E%3Ctext x='40' y='45' font-family='Arial' font-size='12' fill='%23666' text-anchor='middle'%3ENo Icon%3C/text%3E%3C/svg%3E";
                let iconUrl = game.hasIcon ? ('/icon/' + game.id + '.png') : fallbackSvg;
                
                let displayName = game.originalFilename || game.file;
                let fullPath = game.fullPath || "Путь неизвестен";
                let sizeFormatted = formatBytes(game.size); 
                
                let platformBadge = `<span class="badge ${getPlatformClass(game.platform)}" style="margin:0">${game.platform}</span>`;
                let roleBadge = `<span class="badge ${getRoleClass(game.role)}" style="margin:0">${game.role}</span>`;
                
                let errorBadge = game.error ? `<div style="color: #ef5350; font-size: 0.85em; margin-top: 8px; background: rgba(239, 83, 80, 0.1); padding: 6px 10px; border-radius: 4px; border: 1px solid #ef5350;">⚠️ <b>${t.err_lbl || "Ошибка:"}</b> ${game.error}</div>` : '';
                let titleColor = game.error ? '#ef5350' : '#fff';
                let installBtn = game.error ? '' : `<button class="btn-install" onclick="triggerInstall('${game.id}')">${t.btn_install || "Install"}</button>`;
                
                let card = document.createElement('div');
                card.className = 'game-row';
                if (game.error) card.style.borderColor = "#602020";
                
                card.innerHTML = `
                    <img src="${iconUrl}" class="game-icon" alt="Cover" loading="lazy">
                    <div class="game-info">
                        <p class="game-title" style="color: ${titleColor};" title="${game.title}">${game.title}</p>
                        <div class="game-meta">
                            ${platformBadge} 
                            <span class="badge badge-pkg" style="margin:0">PKG</span>
                            ${roleBadge}
                            <span style="color: #81c784; margin-left: 5px;">${game.titleId}</span>
                            <span>• v${game.version} •</span>
                            <span style="color: #64b5f6; font-weight: bold;">${sizeFormatted}</span>
                        </div>
                        <div class="file-line">
                            <span class="game-file" title="${fullPath}">${displayName}</span>
                            <button class="btn-copy" onclick="copyDirectLink('${game.id}')">${t.btn_copy || "🔗 Link"}</button>
                        </div>
                        ${errorBadge}
                    </div>
                    <div class="game-actions">
                        ${installBtn}
                    </div>`;
                container.appendChild(card);
            });
        }

        async function pollPS5Status() {
            let ip = ipInput.value;
            let badge = document.getElementById('conn_status');
            let dash = document.getElementById('ps5_dashboard');
            let pCont = document.getElementById('progress_container');
            
            if (!ip) {
                badge.className = "badge"; badge.innerText = currentLang === 'ru' ? "Укажите IP" : "Set IP";
                dash.style.display = "none";
                pCont.style.display = "none";
                return;
            }
            try {
                let res = await fetch('/api/ps5_status?ip=' + ip);
                let data = await res.json();
                dash.style.display = "flex";
                if (data.online) {
                    badge.className = "badge bg-online"; badge.innerText = "ONLINE";
                    saveSuccessfulIp(ip);
                    
                    let s = data.status;
                    let busyText = "СВОБОДНА";
                    if (s.busy) {
                        busyText = (s.active && s.active > 0) ? ("УСТАНОВКА (" + s.active + ")") : "УСТАНОВКА";
                    }
                    document.getElementById('st_busy').innerText = busyText;
                    document.getElementById('st_busy').style.color = s.busy ? "#81c784" : "#888";
                    
                    if (s.pull && s.pullWant > 0) {
                        pCont.style.display = "block";
                        let percent = ((s.pullGot / s.pullWant) * 100).toFixed(1);
                        document.getElementById('st_progress_bar').style.width = percent + '%';
                        document.getElementById('st_progress_txt').innerText = percent + '%';
                        document.getElementById('st_downloaded').innerText = formatBytes(s.pullGot);
                        document.getElementById('st_total').innerText = formatBytes(s.pullWant);
                    } else {
                        pCont.style.display = "none";
                    }
                } else {
                    badge.className = "badge bg-offline"; badge.innerText = "OFFLINE";
                    document.getElementById('st_busy').innerText = "Ожидание...";
                    document.getElementById('st_busy').style.color = "#888";
                    pCont.style.display = "none";
                }
            } catch(e) {
                badge.className = "badge bg-offline"; badge.innerText = "ERROR";
                dash.style.display = "flex";
                document.getElementById('st_busy').innerText = "Нет связи";
                document.getElementById('st_busy').style.color = "#e57373";
                pCont.style.display = "none";
            }
        }
        
        async function openSettingsModal() {
            try {
                let res = await fetch('/api/config');
                let cfg = await res.json();
                if (cfg.pkg_folder) document.getElementById('cfg_pkg_folder').value = cfg.pkg_folder;
                if (cfg.server_port) document.getElementById('cfg_server_port').value = cfg.server_port;
            } catch(e) {}
            document.getElementById('settings_modal').style.display = 'flex';
        }

        function closeSettingsModal() {
            document.getElementById('settings_modal').style.display = 'none';
        }

        function setFolder(path) {
            document.getElementById('cfg_pkg_folder').value = path;
        }

        async function saveServerConfig() {
            let folder = document.getElementById('cfg_pkg_folder').value.trim();
            let port = parseInt(document.getElementById('cfg_server_port').value.trim()) || 9898;
            if (!folder) {
                showToast('Укажите путь к папке', true);
                return;
            }
            try {
                let res = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({pkg_folder: folder, server_port: port})
                });
                let data = await res.json();
                if (data.status === 'success') {
                    showToast(data.message || 'Настройки сохранены');
                    closeSettingsModal();
                    setTimeout(fetchCatalog, 1000);
                } else {
                    showToast(data.message || 'Ошибка сохранения', true);
                }
            } catch(e) {
                showToast('Ошибка связи с сервером', true);
            }
        }

        async function rescanOnly() {
            try {
                let res = await fetch('/api/rescan', {method: 'POST'});
                let data = await res.json();
                showToast(data.message || 'Сканирование запущено');
                closeSettingsModal();
                setTimeout(fetchCatalog, 1500);
            } catch(e) {
                showToast('Ошибка запуска сканирования', true);
            }
        }

        loadTranslations();
        updateIpDatalist();
        fetchCatalog();
        
        // Мгновенная проверка статуса при загрузке страницы, если IP подставился
        if (ipInput.value) {
            pollPS5Status();
        }
        
        setInterval(updateIpDatalist, 10000);
        setInterval(pollPS5Status, 2000);
        setInterval(fetchCatalog, 5000); 
    </script>
</body>
</html>"""