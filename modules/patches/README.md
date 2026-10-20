# Antigravity Core Binary Patcher (`modules/patches`)

Модуль точечного бинарного патчинга ядра Antigravity (`language_server`) под архитектуру **Android ARM64 (aarch64)**. Обеспечивает обход платформенных ограничений (Android seccomp, Bionic libc, отсутствие LSE atomics на ARMv8.0-A) и интеграцию с runtime-окружением.

---

## 1. Архитектура

```
modules/patches/
├── pipeline.py              # CLI-оркестратор и API запуска пайплайна
├── spec/
│   └── patch_manifest.json  # Спецификация ожидаемых патчей и политик
├── engine/                  # Низкоуровневые движки анализа и модификации
│   ├── elf_scanner.py       # Парсер ELF64/AArch64 и локатор секции .text
│   ├── pclntab_scanner.py   # Парсер таблицы функций Go pclntab и MOVZ-кодировщик
│   ├── byte_replacer.py     # Поиск и in-place замена байтовых паттернов
│   ├── reporter.py          # Формирование JSON-отчетов по выполненным патчам
│   └── patch_context.py     # Модель контекста выполнения
├── groups/                  # Функциональные группы патчей
│   ├── gates/               # Обход CLI gate и Enterprise Auth
│   ├── syscalls/            # Замена seccomp-блокируемых faccessat2/fchmodat2
│   ├── sigill/              # Защита обработчика SIGILL (для liblse_compat)
│   ├── resolv/              # Редирект /etc/resolv.conf на относительный путь
│   └── failfast/            # Подавление проверок CPU ARMv8.0-A и preinit atomic
└── tests/                   # Модульные и интеграционные тесты
    ├── test_byte_replacer.py
    ├── test_elf_scanner.py
    ├── test_pclntab_scanner.py
    ├── test_full_pipeline.py
    └── run_all.sh
```

---

## 2. Группы патчей

| Группа | Модуль | Цель и сигнатура | Действие |
|---|---|---|---|
| **gates** | `cli_gate` | `ldrb w1, [x0,#8]` в проверке CLI gate | Заменяется на `mov w1, #1` (`21 00 80 52`) |
| **gates** | `enterprise_auth` | `EnterpriseAuthValidator.Validate` | Принудительная установка флага валидности |
| **syscalls** | `faccessat` | `syscall.faccessat2` (sys_439: `0xd28036e0`) | Ретаргетинг на `faccessat` (sys_48: `0xd2800600`) |
| **syscalls** | `fchmodat` | `syscall.fchmodat2` (sys_452: `0xd2803880`) | Ретаргетинг на `fchmodat` (sys_53: `0xd28006a0`) |
| **sigill** | `sigill_handler` | Вызов `rt_sigaction` в рантайме Go | Игнорирование сигнала `SIGILL` (4) для сохранения обработчика `liblse_compat.so` |
| **resolv** | `resolv_redirect` | Строка `/etc/resolv.conf` (16 байт) | Замена на `etc//resolv.conf` без изменения длины |
| **failfast** | `crash_suppressor` | ARMv8.0-A CPU feature check (`0x7701180`) & preinit atomic (`0x7765c60`) | Branch `b +0x64` в обход проверки LSE/CRC/AES и замена `ldaddal` на `ldr`/`str` для полной совместимости с процессорами ARMv8.0-A (Snapdragon 660 и др., без аппаратного LSE) |

---

## 3. Оптимизации движков анализа (Заход 1)

1. **`elf_scanner.py`**:
   - Прямая валидация заголовка `e_ident` по смещению 0 с поддержкой поиска встроенных ELF-контейнеров.
   - Поддержка stripped-бинарников (`e_shnum == 0`): автоматический fallback на Program Headers (`PT_LOAD` с флагом `PF_X`).
   - Строгая проверка границ смещений и размеров для секций `.text`, `.shstrtab` и таблиц заголовков.
2. **`pclntab_scanner.py`**:
   - Оптимизированный `find_function`: прямой поиск позиции имени функции в таблице строк `funcnametab`.
   - Внутреннее кэширование результатов поиска функций (`_cache`) в контексте pclntab, исключающее циклы декодирования десятков тысяч строк latin-1 на каждый сисколл.
3. **Zero-Copy в группах патчей**:
   - Полное устранение промежуточных аллокаций `bytes(data)` в циклах сканирования; прямая работа по протоколу буфера (`bytearray` / `memoryview`).
   - Устранение обхода верификации в `crash_suppressor.py`: строгое соблюдение политики fail-closed.

---

## 4. CLI & Python API

### CLI Runner
```bash
# Применение всех патчей к бинарнику:
python3 modules/patches/pipeline.py /path/to/language_server

# С сохранением отчета в manifest:
python3 modules/patches/pipeline.py /path/to/language_server --manifest report.json

# Проверка наличия патчей (exit code 0 / 1):
python3 modules/patches/pipeline.py /path/to/language_server --verify

# Тестовый прогон без записи изменений:
python3 modules/patches/pipeline.py /path/to/language_server --dry-run

# Толерантность к отсутствующим сигнатурам:
python3 modules/patches/pipeline.py /path/to/language_server --allow-missing
```

### Python API
```python
import pipeline

ok = pipeline.run_pipeline(
    target_path="/path/to/language_server",
    verify=False,        # Только верификация
    dry_run=False,       # Прогон без записи на диск
    allow_missing=False, # Не падать при отсутствии сигнатур
    manifest_path=None   # Путь для сохранения JSON-манифеста
)
```

---

## 5. Тестирование

Запуск полного тестового набора:
```bash
bash modules/patches/tests/run_all.sh
```

- `test_byte_replacer.py`: юнит-тесты сопоставления байт и точечной замены.
- `test_elf_scanner.py`: валидация ELF64, fallback на Program Headers для stripped-бинарников и проверка границ.
- `test_pclntab_scanner.py`: валидация кодирования опкодов AArch64 `MOVZ X0, #imm`, прямой поиск в `funcnametab` и кэширование.
- `test_full_pipeline.py`: E2E тест на реальном pristine-бинарнике `language_server` (dry-run, apply, sha256 check, verify, idempotence, fail-closed validation).
