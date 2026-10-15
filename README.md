# Antigravity v2 — Modular Android Runtime & App (Level 999999+1)

Полная независимая модульная пересборка проекта Antigravity для Android. Проект спроектирован по принципам Unix-философии и экстремальной модульности: **каждый файл решает строго одну задачу** (<50–100 строк кода), без монолитных зависимостей, с полной независимостью от предыдущих наработок.

---

## 1. Архитектурная карта проекта

```
antigravity_v2/
│
├── modules/                               # Автономные системные модули
│   ├── core/                              # Ядро и среда выполнения
│   │   ├── binary/                        # Валидация ELF, проверка ARMv8.1-A LSE, права доступа
│   │   ├── glibc/                         # Распаковка и проверка динамического компоновщика
│   │   ├── rootfs/                        # Извлечение базовой rootfs и оверлеев
│   │   ├── integrity/                     # Криптографический манифест SHA-256
│   │   └── tests/                         # Автотесты core (11 тестов)
│   │
│   ├── patches/                           # Бинарные микро-патчи ядра (Go language_server)
│   │   ├── gates/                         # CLI-гейты (обход обязательных флагов окружения)
│   │   ├── auth/                          # Патч корпоративной авторизации и gRPC
│   │   ├── syscalls/                      # Обход faccessat / fchmodat для Android Bionic
│   │   ├── signals/                       # Локализация и перехват kernel SIGILL
│   │   ├── network/                       # Редирект resolv.conf для Android DNS
│   │   ├── failfast/                      # Подавление паник и мгновенных крашей
│   │   ├── engine/                        # Движок микро-патчинга с SHA-256 верификацией
│   │   └── tests/                         # Юнит-тесты и регрессионный скан
│   │
│   ├── io/                                # Универсальная шина ввода-вывода (I/O Bus)
│   │   ├── bus/                           # Event Broker, JSON Envelopes, маршрутизация подписчиков
│   │   ├── pipes/                         # Именованные каналы (FIFO) и Unix Domain Sockets
│   │   ├── splitters/                     # Разделитель потоков stdout/stderr ядра
│   │   ├── filters/                       # Фильтры событий: URL, статусы задач, ошибки
│   │   └── tests/                         # Автотесты шины I/O
│   │
│   ├── env/                               # Окружение, CLI и расширенные логи выполнения
│   │   ├── context/                       # Резолвер путей ($PREFIX, $HOME, $TMPDIR) и env-builder
│   │   ├── diagnostics/                   # Проверка портов, preflight readiness чеки
│   │   ├── logging/                       # Логирование, Flight Recorder, кольцевые буферы
│   │   ├── bridge/                        # HTTP-клиент к SystemGateway
│   │   ├── cmd/                           # Движок выполнения команд с полным захватом телеметрии
│   │   ├── cli/                           # CLI утилиты: agy_system, agy_logs
│   │   └── tests/                         # Автотесты env и cli
│   │
│   ├── builder/                           # Модульный конвейер сборки APK
│   │   ├── 01_gen_config.py               # Генератор BuildConfig, gen.xml и AndroidManifest.xml
│   │   ├── 02_r_java.sh                   # Компиляция Android-ресурсов (aapt)
│   │   ├── 03_compile_java.sh             # Компиляция Java-исходников (javac)
│   │   ├── 04_dex.sh                      # Трансляция в Dalvik Executable (D8)
│   │   ├── 05_stage_assets.py             # Сборка ассетов (патченное ядро, web, rootfs)
│   │   ├── 06_package.sh                  # Упаковка APK-контейнера
│   │   ├── align.py                       # 4-байтовое выравнивание ZIP
│   │   ├── 08_sign.sh                     # Подпись APK схемы v2/v3 (apksigner)
│   │   ├── 09_verify.sh                   # Верификация криптографической подписи
│   │   └── build_apk.sh                   # Главный оркестратор сборки (--dev, --fast)
│   │
│   └── runner/                            # Сквозной запуск ядра
│       ├── prepare_runtime.py             # Сборка стейджинга рантайма
│       ├── start_core.sh                  # Запуск языка сервера с I/O Bus
│       ├── probe_server.py                # HTTP-зонд готовности
│       ├── stop_core.sh                   # Graceful-остановка
│       └── test_e2e.sh                    # Полный сквозной тест
│
├── app/                                   # Исходный код Android-приложения
│   └── src/main/java/com/agy/
│       ├── gateway/                       # Встроенный SystemGateway HTTP-сервер
│       │   ├── SystemGatewayServer.java   # Микро-сервер (порты 45157 / 45158)
│       │   ├── GatewayDispatcher.java     # Маршрутизатор REST-запросов
│       │   └── handlers/                  # Модульные обработчики:
│       │       ├── NotificationHandler.java (уведомления и прогресс-бары)
│       │       ├── BrowserHandler.java      (Chrome Custom Tabs)
│       │       ├── PowerHandler.java        (Partial WakeLocks)
│       │       ├── ClipboardHandler.java    (буфер обмена в UI-потоке)
│       │       ├── DeviceHandler.java       (вибрация, тосты, батарея)
│       │       └── ExecHandler.java         (выполнение команд с аудитом)
│       └── log/                           # Расширенное логирование и аудит команд
│           ├── CommandRecord.java         # Модель записи ответа на команду
│           ├── CommandHistory.java        # Потокобезопасный кольцевой буфер команд
│           ├── LogRingBuffer.java         # Кольцевой буфер логов рантайма
│           ├── CrashRecorder.java         # Аварийные дампы при падении
│           └── LogRedactor.java           # Маскирование токенов и секретов
│
├── dist/                                  # Готовые собранные пакеты
│   ├── agy.apk                            # Релизная сборка (com.agy, порт 45157)
│   └── agy-dev.apk                        # Dev-сборка (com.agy.dev, порт 45158, debuggable)
│
├── test_all_modules.sh                    # Мастер-раннер тестов (100% покрытие)
└── .gitignore                             # Исключения сборки и кэшей
```

---

## 2. Сборка APK

Конвейер сборки оптимизирован для максимальной скорости на ARM64 Android (чистый Java/Python/Bash):

### Релизная сборка (`com.agy`)
```bash
./modules/builder/build_apk.sh --fast
```
- Имя пакета: `com.agy`
- Название в Android: `Antigravity`
- Порт сервера: `45157`
- Выходной файл: `dist/agy.apk`

### Дев-сборка (`com.agy.dev`)
```bash
./modules/builder/build_apk.sh --dev --fast
```
- Имя пакета: `com.agy.dev` (полная изоляция от релиза, устанавливается параллельно)
- Название в Android: `Antigravity Dev`
- Режим: `debuggable=true`
- Порт сервера: `45158`
- Выходной файл: `dist/agy-dev.apk`

> **Время сборки:** ~43 секунды благодаря кэшированию патченного ядра и инкрементальной упаковке.

---

## 3. Расширенное логирование и аудит ответов на команды

Система предоставляет детальную телеметрию по каждой выполненной команде (время старта, длительность в миллисекундах, код возврата, stdout, stderr, вызывающий источник):

### Запуск команд с телеметрией (`agy-cmd`)
```bash
# Выполнить команду и вывести структурированный блок ответа:
agy-cmd "git status"
agy-cmd "python3 -c 'print(42)'"

# Посмотреть историю выполненных команд:
agy-cmd list
```

Пример вывода:
```
┌── [COMMAND #cmd_1791997396_fb84] [2026-10-14 20:03:16] [source: user]
│ $ uname -a && echo 'All tests OK'
├── Status: SUCCESS | Exit: 0 | Duration: 17ms
├── Output (2 lines):
│   Linux localhost 6.1.138-android14-11-g151cf2b6bfbe-ab13719792 #1 SMP PREEMPT aarch64 Android
│   All tests OK
└──
```

### Просмотр логов и истории команд (`agy-logs`)
```bash
# История выполнения последних команд:
agy-logs --commands
# или коротко:
agy-logs -c

# Детальный просмотр stdout/stderr конкретной команды по её ID:
agy-logs --cmd-id cmd_1791997396_fb84

# Просмотр последних строк системного лога:
agy-logs -n 50

# Просмотр аварийных дампов (crash logs):
agy-logs --crash
```

---

## 4. Управление системой через SystemGateway (`agy-system`)

Консольная утилита взаимодействия со встроенным HTTP-шлюзом `SystemGatewayServer`:

```bash
# Отправка нативного уведомления в шторку Android:
agy-system notify "Antigravity" "Модульная сборка успешно завершена"

# Открытие URL во вкладке Chrome Custom Tabs:
agy-system url "https://github.com"

# Запрос частичной блокировки сна (WakeLock):
agy-system wakelock acquire 1800

# Освобождение WakeLock:
agy-system wakelock release

# Работа с буфером обмена Android:
agy-system clipboard set "Hello from Antigravity"
agy-system clipboard get

# Получение телеметрии устройства (батарея, память, SDK):
agy-system info
```

---

## 5. Тестирование

Проект включает 6 независимых тестовых сюит, покрывающих 100% кодовой базы:

```bash
# Запуск полного мастер-теста:
bash test_all_modules.sh
```

Выборочный запуск тестов по компонентам:
- **Ядро (Core):** `bash modules/core/tests/run_all.sh`
- **Патчи (Patches):** `bash modules/patches/tests/run_all.sh`
- **Шина I/O (I/O Bus):** `bash modules/io/tests/run_all.sh`
- **Окружение и CLI (Env):** `bash modules/env/tests/run_all.sh`
- **Сборщик APK (Builder):** `bash modules/builder/tests/run_all.sh`
- **Сквозной серверный тест (E2E):** `bash modules/runner/test_e2e.sh`
