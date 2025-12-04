# Структура проекта

## Основные модули

### `main.py`
**Назначение:** Точка входа в приложение
- Инициализация всех компонентов
- Запуск бота и scheduler
- Обработка graceful shutdown
- Валидация конфигурации

### `bot/` - Пакет Telegram бота

#### `bot/core.py`
**Назначение:** Инициализация и настройка бота
- Класс `SummaryBot` - основной класс бота
- `build_application()` - регистрация всех обработчиков

#### `bot/commands.py`
**Назначение:** Обработчики команд пользователя
- `cmd_start()` - приветствие и инструкции
- `cmd_help()` - справка по командам
- `cmd_add_channel()` - добавление канала
- `cmd_remove_channel()` - удаление канала
- `cmd_list_channels()` - список каналов
- `cmd_set_period()` - настройка периода
- `cmd_manual_summary()` - ручная генерация саммари

#### `bot/callbacks.py`
**Назначение:** Обработчики callback-кнопок
- `handle_callback()` - роутер для inline кнопок
- `send_scheduled_summaries()` - автоматическая отправка по расписанию
- Обработка кнопок period, remove, summary и др.

#### `bot/summarizer.py`
**Назначение:** Генерация саммари через OpenRouter API
- `generate_summary()` - создание саммари одного канала
- `generate_multi_channel_summary()` - саммари нескольких каналов
- `_format_messages()` - форматирование сообщений для LLM

#### `bot/helpers.py`
**Назначение:** Вспомогательные функции
- `send_long_message()` - разбиение длинных сообщений
- `validate_channel_username()` - валидация имени канала
- Прочие утилиты

#### `bot/messages.py`
**Назначение:** Шаблоны сообщений и текстовые константы

### `client.py`
**Назначение:** Работа с Telegram API через Telethon
- Авторизация пользовательского аккаунта
- Чтение сообщений из каналов (публичных и приватных)
- Проверка доступа к каналам

**Ключевые функции:**
- `start()` - запуск Telegram клиента
- `get_channel_info()` - получение ID и названия канала
- `read_channel_messages()` - чтение сообщений за период
- `check_channel_access()` - проверка доступа

### `database.py`
**Назначение:** Работа с SQLite базой данных

**Таблицы:**
- `users` - пользователи бота и их настройки
- `channels` - отслеживаемые каналы

**Ключевые функции:**
- `init_db()` - создание таблиц
- `add_user()` - добавление пользователя
- `add_channel()` - добавление канала в отслеживание
- `get_user_channels()` - получение списка каналов пользователя
- `set_summary_period()` - установка периода
- `get_users_for_summary()` - получение пользователей для отправки

### `scheduler.py`
**Назначение:** Планирование автоматической отправки саммари
- Интеграция с APScheduler
- Проверка необходимости отправки каждый час

### `config.py`
**Назначение:** Управление конфигурацией
- Загрузка переменных окружения из `.env`
- Валидация обязательных параметров

## Утилиты и скрипты

### `setup.sh`
Установка зависимостей и создание виртуального окружения.

### `run.sh`
Запуск бота с проверкой конфигурации.

### `check_config.py`
Проверка корректности `.env` файла.

## Конфигурация

### `.env.example`
Пример файла конфигурации:
- BOT_TOKEN
- API_ID и API_HASH
- OPENROUTER_API_KEY
- OPENROUTER_MODEL
- DATABASE_PATH
- SESSION_NAME

### `telegram-summary-bot.service`
Systemd service файл для запуска бота как системного сервиса.

## Архитектура

```
┌─────────────┐
│   main.py   │  <- Точка входа
└──────┬──────┘
       │
       ├──────────────────────────────────┐
       │                                  │
       ▼                                  ▼
┌─────────────┐                   ┌──────────────┐
│    bot/     │<──────────────────┤ scheduler.py │
│  (пакет)    │                   └──────────────┘
└──────┬──────┘
       │
       ├────────────┬────────────┐
       ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌────────┐
│client.py │  │database  │  │config  │
│(Telethon)│  │  .py     │  │  .py   │
└──────────┘  └──────────┘  └────────┘
       │            │            │
       ▼            ▼            ▼
   Telegram      SQLite        .env
     API          DB
```

## Поток данных

1. **Пользователь** -> команда -> **bot/commands.py**
2. **bot/** -> проверка доступа -> **client.py** -> Telegram API
3. **bot/** -> сохранение -> **database.py** -> SQLite
4. **scheduler.py** -> проверка времени -> **bot/callbacks.py**
5. **bot/** -> чтение сообщений -> **client.py** -> Telegram API
6. **bot/** -> генерация саммари -> **bot/summarizer.py** -> OpenRouter API
7. **bot/** -> отправка саммари -> Пользователь

## Зависимости модулей

- `main.py` -> `bot/`, `scheduler.py`, `config.py`
- `bot/core.py` -> `bot/commands.py`, `bot/callbacks.py`, `client.py`, `database.py`
- `bot/commands.py` -> `bot/helpers.py`, `bot/messages.py`, `database.py`, `client.py`
- `bot/callbacks.py` -> `bot/summarizer.py`, `bot/helpers.py`, `database.py`, `client.py`
- `bot/summarizer.py` -> `config.py`
- `client.py` -> `config.py`
- `database.py` -> `config.py`
- `config.py` -> `.env`

## Рекомендации по разработке

### Добавление новой команды
1. Добавьте обработчик в `bot/commands.py`
2. Зарегистрируйте в `bot/core.py:build_application()`
3. Добавьте описание в `/help` команду
4. Обновите `README.md`

### Добавление нового callback-обработчика
1. Добавьте обработчик в `bot/callbacks.py`
2. Зарегистрируйте паттерн в `handle_callback()` или добавьте новый CallbackQueryHandler

### Добавление нового поля в БД
1. Измените схему в `database.py:init_db()`
2. Добавьте методы для работы с полем
3. Обновите код использования в `bot/`

### Изменение формата саммари
1. Измените промпт в `bot/summarizer.py:generate_summary()`
2. При необходимости измените форматирование в `_format_messages()`

### Изменение периодичности проверки
1. Измените CronTrigger в `scheduler.py:start()`
