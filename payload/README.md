# PS5 PKG Receiver Payload (LoopDPI)

Standalone daemon for PlayStation 5 (FreeBSD/Prospero) that runs in the background and accepts Direct Package Installer (DPI) requests over HTTP, triggers native package installations via Sony's `AppInstUtil`, and broadcasts UDP discovery beacons.

---

## 📁 Модульная структура `payload/`

Исходный код разделен на понятные логические модули с комментариями:

- **`common.h`** — общие определения, заголовочные файлы, порты, лимиты и глобальное состояние.
- **`notify.h` / `notify.c`** — вывод системных уведомлений (toast) на экран PS5 (`sceKernelSendNotificationRequest`).
- **`installer.h` / `installer.c`** — динамическая интеграция с `libSceAppInstUtil.sprx` и очередь задач установки PKG.
- **`launcher.h` / `launcher.c`** — регистрация постоянного ярлыка "PKGri" (PKGS12800) в главном меню PS5.
- **`http_helpers.h` / `http_helpers.c`** — отправка ответов (JSON, HTML, PNG, text) и легковесный парсер URL / JSON.
- **`storage.h` / `storage.c`** — сканирование накопителей (`/data`, `/mnt/usb0..7`, `/mnt/ext0`, `/mnt/ext1`) и дисковое пространство.
- **`webui.h` / `webui.c`** — встроенная веб-страница управления со списком игр, поиском, мониторингом памяти и установкой PKG.
- **`beacon.h` / `beacon.c`** — сетевое обнаружение: рассылка UDP 12801 маяков и приём UDP 12802 анонсов от ПК/NAS.
- **`http_server.h` / `http_server.c`** — обработчик входящих HTTP-подключений и роутинг REST API эндпоинтов.
- **`main.c`** — точка входа: инициализация, защита от дубликатов, сетевой watchdog и восстановление после сна (Standby).
- **`Makefile`** — компиляция проекта для PS5 (`make`) и для ПК/Linux (`make host`).
- **`build.sh`** — удобный скрипт для сборки с поддержкой Docker и Host режимов.
- **`Dockerfile`** — автономное сборочное окружение с SDK.
- **`icon0.png`** / **`logo.png`** / **`launcher_param.json`** — бинарные ресурсы ярлыка (вкомпилируются через `.incbin`).
- **`serve_pkg.py`** — локальный тестовый HTTP-сервер на Python с поддержкой HTTP 206 Range.

---

## 🛠️ Сборка

### Вариант 1. Сборка через PS5 Payload SDK

Вам потребуется установленный SDK [ps5-payload-dev/sdk](https://github.com/ps5-payload-dev/sdk) и LLVM/Clang.

1. Установите переменную окружения с путем к SDK:
   ```bash
   export PS5_PAYLOAD_SDK=/opt/ps5-payload-sdk
   ```
2. Соберите бинарник:
   ```bash
   make
   # или
   ./build.sh
   ```
   На выходе получится файл **`pkg-receiver.elf`**.

3. Очистка временных файлов:
   ```bash
   make clean
   ```

---

### Вариант 2. Сборка через Docker (без установки SDK на хост)

Если не хочется вручную собирать тулчейн Prospero/LLVM:

```bash
./build.sh --docker
```
Скрипт автоматически соберет Docker-образ с тулчейном и скомпилирует `pkg-receiver.elf` в текущую папку.

---

### Вариант 3. Сборка под хост (Linux / WSL) для отладки

Для проверки API, роутинга и сетевых протоколов прямо на компьютере:

```bash
make host
# или
./build.sh --host
```
Запуск локального сервера-эмулятора:
```bash
./pkg-receiver-host
```

---

## 🚀 Загрузка на консоль (Отправка ELF)

Отправьте скомпилированный `pkg-receiver.elf` на консоль PS5 через любой стандартный Payload Loader (порт 9021 или 9020):

```bash
# Через netcat:
nc -w 3 <IP_PS5> 9021 < pkg-receiver.elf

# Или через socat:
socat -u FILE:pkg-receiver.elf TCP:<IP_PS5>:9021
```

После загрузки на экране PS5 появится всплывающее системное уведомление (toast):  
`PKGri: listening on 12800`

---

## 🌐 Сетевые порты и протоколы

| Порт / Протокол | Назначение | Описание |
|-----------------|------------|----------|
| **12800 TCP** | HTTP REST API & WebUI | Основной сервер управления, прием команд `/api/install`, отображение статуса `/api/status`, версия `/api/version` и встроенная веб-страница управления. |
| **12801 UDP** | Beacon Broadcast | Пейлоад каждые 2 секунды рассылает broadcast-пакет `PKGSENDER v1` в локальную подсеть для автообнаружения консоли в приложении на ПК / Android. |
| **12802 UDP** | PC Discovery Listener | Слушает анонсы от ПК (`PKGSENDER-PC <IP>:<PORT>`) для быстрого сопряжения. |

---

## 🛡️ Отказоустойчивость (Rest Mode / Переподключение сети)

В `main.c` реализована защита от обрыва сетевого интерфейса:
- При уходе консоли в **Rest Mode** или смене сети (Wi-Fi ↔ LAN) сокеты не зависают.
- Цикл `accept()` перехватывает ошибки `EBADF`, `EINVAL`, `ENETDOWN` и автоматически пересоздает слушающий сокет с опциями `SO_REUSEADDR` и `SO_REUSEPORT`.
- При возобновлении связи на консоль выводится тост: `PKGri: network restored\nIP: ...`.
