# Gimmel Discord Absence Bot

Discord-бот считает календарные дни отсутствия пользователей в voice/stage каналах и публикует ежедневный отчёт в выбранный канал.

## Что умеет

- Трекинг активности по `VOICE_STATE_UPDATE`:
  - вход в voice/stage канал;
  - переход между voice/stage каналами;
  - игнор mute/deaf изменений без смены канала.
- Ежедневная отправка отчёта по расписанию (`timezone` + `daily_time`).
- Slash-команды `/absence ...` для админа и пользователя.
- Privacy-функции: `status`, `privacy`, `optout`.
- Безопасные упоминания: по умолчанию `allowed_mentions = {"parse": []}`.
- Health endpoints: `/healthz`, `/readyz`.

## Требования

- Python 3.9+
- Discord bot token
- Для VPS: `systemd`

## Быстрый локальный запуск

```bash
cd Gimmel-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
cp .env.example .env
```

Заполните `DISCORD_TOKEN` в `.env`.

Запуск:

```bash
set -a; source .env; set +a
PYTHONPATH=src python -m absence_bot.main
```

Проверка:

```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
```

`readyz = ready` означает, что storage и Discord gateway готовы.

## Тесты

```bash
PYTHONPATH=src pytest
```

## Переменные окружения

- `DISCORD_TOKEN` (обязательно)
- `DATABASE_URL` (по умолчанию `sqlite:///./absence_bot.db`)
- `HTTP_HOST` (по умолчанию `127.0.0.1`)
- `HTTP_PORT` (по умолчанию `8080`)
- `LOG_LEVEL` (по умолчанию `INFO`)
- `DEFAULT_TIMEZONE` (по умолчанию `UTC`)
- `DEFAULT_DAILY_TIME` (по умолчанию `09:00`)
- `DEFAULT_TEMPLATE` (в `.env` должен быть в кавычках)
- `RETENTION_DAYS` (по умолчанию `30`)

## Команды бота

Админ-команды:

- `/absence add user:<user> [display_name_override:<text>]` - добавить пользователя в отслеживание.
- `/absence remove user:<user>` - убрать пользователя из отслеживания.
- `/absence list [page:<int>]` - показать список отслеживаемых пользователей и их статус.
- `/absence enable` - включить ежедневную отправку отчётов для сервера.
- `/absence disable` - отключить ежедневную отправку отчётов для сервера.
- `/absence configure-channel channel:<text_channel>` - выбрать канал, куда бот публикует отчёты.
- `/absence set-timezone tz:<IANA_TZ>` - установить таймзону сервера (например, `Europe/Moscow`).
- `/absence set-template template:<text>` - задать шаблон текста отчёта.
- `/absence set-post-mode mode:<single|per_user>` - выбрать формат публикации: один сводный пост или отдельный пост по каждому пользователю.
- `/absence set-mention-mode mode:<no_ping|ping>` - включить/выключить реальные пинги пользователей.
- `/absence run` - вручную запустить отчёт прямо сейчас (имитация плановой отправки).

Пользовательские:

- `/absence optout mode:<enable|disable> [reason:<text>]` - включить или выключить отказ от отслеживания себя.
- `/absence status` - показать, отслеживается ли пользователь, есть ли opt-out и какая дата последнего визита сохранена.
- `/absence privacy` - показать, какие данные хранит бот и как работает политика удаления.

## Как пригласить бота на сервер

В Discord Developer Portal (`OAuth2 -> URL Generator`) выберите:

- Scopes: `bot`, `applications.commands`
- Bot Permissions: минимум `View Channels`, `Send Messages`

После добавления бота на сервер настройте:

1. `/absence configure-channel`
2. `/absence set-timezone`
3. `/absence add`
4. `/absence run`

## Деплой на Ubuntu VPS через systemd

### 1) Установка и запуск

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip curl

sudo adduser --disabled-password --gecos "" bot
sudo mkdir -p /opt
sudo chown -R bot:bot /opt

sudo -u bot -H bash -lc '
  git clone https://github.com/ASarafanov/Gimmel-discord-bot.git /opt/Gimmel-discord-bot
  cd /opt/Gimmel-discord-bot/Gimmel-bot
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -U pip
  python -m pip install -e .[dev]
  cp .env.example .env
  mkdir -p data
'
```

Заполните `/opt/Gimmel-discord-bot/Gimmel-bot/.env`.
Рекомендуемый `DATABASE_URL` на VPS:

```env
DATABASE_URL=sqlite:////opt/Gimmel-discord-bot/Gimmel-bot/data/absence_bot.db
```

### 2) systemd unit

```bash
sudo tee /etc/systemd/system/gimmel-bot.service >/dev/null <<'EOF_SERVICE'
[Unit]
Description=Gimmel Discord Absence Bot
After=network.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/Gimmel-discord-bot/Gimmel-bot
EnvironmentFile=/opt/Gimmel-discord-bot/Gimmel-bot/.env
ExecStart=/opt/Gimmel-discord-bot/Gimmel-bot/.venv/bin/python -m absence_bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF_SERVICE

sudo systemctl daemon-reload
sudo systemctl enable --now gimmel-bot
sudo systemctl status gimmel-bot --no-pager -l
```

### 3) Проверка на VPS

```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
journalctl -u gimmel-bot -f -l
```

## Опционально: запуск через Xray/VLESS (proxychains)

Если VPS не может напрямую достучаться до Discord API, можно запускать бот через SOCKS5 (`xray` + `proxychains4`).

В `gimmel-bot.service` замените `ExecStart`:

```ini
ExecStart=/usr/bin/proxychains4 -q /opt/Gimmel-discord-bot/Gimmel-bot/.venv/bin/python -m absence_bot.main
```

И добавьте зависимости:

```ini
After=network.target xray.service
Wants=xray.service
```

## Частые проблемы

- `readyz = not_ready`:
  - проверьте, что валиден `DISCORD_TOKEN`;
  - проверьте доступ VPS к `https://discord.com/api/v10/gateway`;
  - смотрите `journalctl -u gimmel-bot -f -l`.
- `FileNotFoundError ... schema.sql`:
  - используйте `python -m pip install -e .[dev]`.
- Slash-команды не видны сразу:
  - подождите несколько минут после старта бота (`tree.sync()` глобальный).

## Безопасность

- Не коммитьте `.env` и ключи.
- Регулярно ротируйте `DISCORD_TOKEN`.
- Не публикуйте приватные VLESS/SSH ключи.
