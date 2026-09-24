# PS5 PKG Sender & Receiver (Payload & NAS Server)

Система удаленной установки PKG-пакетов для PlayStation 5 (а также PS4), состоящая из двух компонентов:
1. **`payload/` (PKGri)** — автономный фоновый C-демон для PS5 (FreeBSD/Prospero), принимающий команды установки, управляющий процессом через Sony `AppInstUtil`, опрашивающий внутренний и USB-накопители и рассылающий маяки обнаружения.
2. **`server/` (NAS / PC Backend)** — легковесный сервер на Python (для Synology DSM, Linux, Windows, macOS), с автоматическим отслеживанием файлов (Watchdog), парсером заголовков PKG (`\x7FCNT` / `\x7FFIH`), базой SQLite, HTTP Range сервером (порт 9898), UDP-анонсером и адаптивным мультиязычным веб-интерфейсом.

---

## 📁 Структура проекта

```text
├── server/                 # Серверная часть (NAS / PC) на Python
│   ├── main.py             # Точка входа сервера, управление потоками и Graceful Shutdown
│   ├── server.py           # HTTP сервер (порт 9898, Range 206, REST API, UDP Broadcaster 12802)
│   ├── scanner.py          # Служба мониторинга каталога с играми (Watchdog + сборка мусора)
│   ├── parser.py           # Парсер метаданных PKG (SFO, param.json, извлечение icon0)
│   ├── db.py               # Работа с NoSQL/JSON базой данных на SQLite (catalog.db)
│   ├── feedback.py         # Генератор WebUI, трекинг IP консолей
│   ├── config.py / .json   # Конфигурация путей к играм и порта сервера
│   ├── logger.py           # Ротация логов (до 100 строк в app.log)
│   └── locales.json        # Локализация интерфейса (RU, EN, FR, DE, ES, JA)
├── payload/                # Клиентский демон для PS5 (C / Prospero)
│   ├── main.c              # Исходный код демона (Prospero / POSIX, WebUI, HTTP/UDP, Standby)
│   ├── Makefile            # Сборочные правила для PS5 ELF и хост-отладки (make, make host)
│   ├── build.sh            # Скрипт сборки (PS5 SDK, --host, --docker, --clean)
│   ├── Dockerfile          # Автономное Docker-окружение со сборочным тулчейном PS5 SDK
│   ├── icon0.png           # Иконка для лаунчера на главном экране PS5
│   ├── logo.png            # Логотип лаунчера
│   ├── launcher_param.json # Манифест лаунчера для Prospero
│   ├── pkg-receiver.elf    # Скомпилированный бинарный файл для отправки на PS5
│   └── README.md           # Документация пейлоада
├── index.html              # Встроенный Web-интерфейс управления пейлоадом (порт 12800)
└── package.json            # Vite-конфигурация для предпросмотра WebUI
```

---

## 🛠️ Сборка

### Вариант 1. Сборка через PS5 Payload SDK
Требуются установленный SDK [ps5-payload-dev/sdk](https://github.com/ps5-payload-dev/sdk) и LLVM/Clang:
```bash
export PS5_PAYLOAD_SDK=/opt/ps5-payload-sdk
cd payload
make
# или из корня:
./payload/build.sh
```
Результат сборки: `payload/pkg-receiver.elf`.

### Вариант 2. Сборка через Docker (без установки SDK на хост)
```bash
./payload/build.sh --docker
```
Скрипт собирает изолированный образ с тулчейном и компилирует чистый ELF-файл.

### Вариант 3. Сборка под хост (Linux / macOS / WSL) для тестирования
```bash
./payload/build.sh --host
# Запуск локального демона для тестирования API:
./payload/pkg-receiver-host
```

---

## 🚀 Запуск на консоли

Отправьте `pkg-receiver.elf` на консоль PS5 через Payload Loader (порт 9021 или 9020):
```bash
# Через netcat:
nc -w 3 <IP_PS5> 9021 < payload/pkg-receiver.elf

# Или через socat:
socat -u FILE:payload/pkg-receiver.elf TCP:<IP_PS5>:9021
```

После загрузки на экране консоли появится системное уведомление:
```text
PKGri: listening on 12800
IP: <IP_PS5>
```

---

## 🌐 Сетевые порты и протоколы

| Порт / Протокол | Назначение | Описание |
|-----------------|------------|----------|
| **12800 TCP** | HTTP REST API & WebUI | Основной сервер: веб-интерфейс, прием команд установки `/api/install`, мониторинг `/api/status`, свободное место `/api/space`. |
| **12801 UDP** | Discovery Beacon | Каждые 3 секунды рассылает broadcast `PKGSENDER v1` в локальную подсеть для автообнаружения консоли. |
| **12802 UDP** | PC Announce Listener | Принимает анонсы от ПК (`PKGSENDER-PC <IP>:<PORT>`) для быстрого сопряжения. |

---

## 📡 HTTP API эндпоинты

- **`GET /`** — Встроенный веб-интерфейс (управление очередью, просмотр каталога, ручная установка по URL).
- **`GET /api/status`** — Текущее состояние установки:
  ```json
  {"busy": false, "active": 0, "pull": false, "pullName": "", "pullGot": 0, "pullWant": -1, "pullPaused": false}
  ```
- **`GET /api/space`** — Свободное место на встроенном накопителе (`/data`) и подключенных USB-накопителях (`/mnt/usb0`..`/mnt/usb7`, `/mnt/ext0`, `/mnt/ext1`):
  ```json
  {
    "free": 214748364800,
    "total": 858993459200,
    "internal": { "path": "/data", "free": 214748364800, "total": 858993459200 },
    "usb": [
      { "name": "USB 0", "path": "/mnt/usb0", "free": 64424509440, "total": 128849018880 }
    ]
  }
  ```
- **`POST /api/install`** — Запуск установки PKG по HTTP-ссылке:
  ```json
  {"packages": ["http://192.168.1.100:9898/game.pkg"]}
  ```
- **`GET /api/version`** — Версия пейлоада и сборки.
- **`GET /api/pc`** — Адрес последнего обнаруженного сервера на ПК.

---

## 🛡️ Отказоустойчивость и поддержка режима ожидания (Standby / Rest Mode)

- **Перехват `SIGCONT` (Wake-up Recovery):** При выходе консоли из режима ожидания сервер мгновенно перехватывает сигнал, ожидает 1 секунду для стабилизации сетевого стека `SceNet`, пересоздает сокет с `SO_REUSEADDR` / `SO_REUSEPORT` и выводит уведомление на экран.
- **Сетевой вотчдог (каждые 5 секунд):** Автоматически отслеживает изменение локального IP консоли или переподключение Wi-Fi/LAN. При потере внешней сети сервер продолжает работать для локальных запросов через loopback (`127.0.0.1:12800`).
- **UDP воркеры:** Сокеты маяков и приема анонсов автоматически восстанавливаются при сбоях сети (`ENETDOWN`, `EBADF`).

---

## 💡 Лицензия и благодарности

- [ps5-payload-dev/sdk](https://github.com/ps5-payload-dev/sdk) — тулчейн и заголовочные файлы для сборки ELF под PS5 Prospero.
- [ps5-payload-manager](https://github.com/itsPLK/ps5-payload-manager) — паттерны восстановления соединения после Standby и сетевой вотчдог.
- [seregonwar/zftpd](https://github.com/seregonwar/zftpd) — рекомендации по оптимизации буферов сокетов для PS5.
- [ps5-web-file-manager](https://github.com/owendswang/ps5-web-file-manager) — концепция веб-ярлыка на главном экране.

