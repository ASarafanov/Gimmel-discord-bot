# Discord Absence Bot

Бот считает календарные дни отсутствия отслеживаемых пользователей в voice/stage каналах и публикует ежедневный отчёт.

## Возможности

- Трекинг активности по `VOICE_STATE_UPDATE` (вход и перемещение между каналами)
- Ежедневные отчёты по расписанию с учётом `timezone` и `daily_time`
- Slash-команды `/absence ...` для админов и пользователей
- Privacy-команды: `privacy`, `status`, `optout`
- Безопасные упоминания: по умолчанию `allowed_mentions.parse=[]`
- Хранилище SQLite + интерфейс под Postgres
- Health endpoints: `/healthz`, `/readyz`

## Быстрый старт

1. Создайте и активируйте виртуальное окружение.
2. Установите зависимости:

```bash
python3 -m pip install -e .[dev]
```

3. Скопируйте `.env.example` в `.env` и заполните `DISCORD_TOKEN`.
4. Запустите:

```bash
python3 -m absence_bot.main
```

## Переменные окружения

- `DISCORD_TOKEN` (обязательно)
- `DATABASE_URL` (по умолчанию `sqlite:///./absence_bot.db`)
- `HTTP_HOST` (по умолчанию `127.0.0.1`)
- `HTTP_PORT` (по умолчанию `8080`)
- `LOG_LEVEL` (по умолчанию `INFO`)
- `DEFAULT_TIMEZONE` (по умолчанию `UTC`)
- `DEFAULT_DAILY_TIME` (по умолчанию `09:00`)
- `DEFAULT_TEMPLATE`
- `RETENTION_DAYS` (по умолчанию `30`)

## Тесты

```bash
pytest
```

## Команды

Админ-команды:
- `/absence add`
- `/absence remove`
- `/absence list`
- `/absence enable` / `/absence disable`
- `/absence configure-channel`
- `/absence set-timezone`
- `/absence set-template`
- `/absence set-post-mode`
- `/absence set-mention-mode`
- `/absence run`

Пользовательские:
- `/absence optout`
- `/absence status`
- `/absence privacy`

## Безопасность

- Не храните токен бота в репозитории.
- Логи не должны содержать секреты.
- По умолчанию пинги отключены через `allowed_mentions`.
