from __future__ import annotations

import os
from dataclasses import dataclass

from .time_utils import validate_daily_time, validate_timezone


@dataclass
class Settings:
    discord_token: str
    database_url: str
    http_host: str
    http_port: int
    log_level: str
    default_timezone: str
    default_daily_time: str
    default_template: str
    retention_days: int
    max_send_retries: int = 5

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite:///")

    @property
    def sqlite_path(self) -> str:
        if not self.is_sqlite:
            raise ValueError("Only sqlite:/// URLs are supported by sqlite adapter")
        return self.database_url.removeprefix("sqlite:///")

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise ValueError("DISCORD_TOKEN is required")

        database_url = os.getenv("DATABASE_URL", "sqlite:///./absence_bot.db").strip()
        http_host = os.getenv("HTTP_HOST", "127.0.0.1").strip()
        http_port = int(os.getenv("HTTP_PORT", "8080"))
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        default_timezone = os.getenv("DEFAULT_TIMEZONE", "UTC").strip()
        default_daily_time = os.getenv("DEFAULT_DAILY_TIME", "09:00").strip()
        default_template = os.getenv(
            "DEFAULT_TEMPLATE",
            "Прошло **{days} {days_word}** с момента ~~смерти героя Гиммеля~~ как {display_name} покинул нас.",
        ).strip()
        retention_days = int(os.getenv("RETENTION_DAYS", "30"))

        validate_timezone(default_timezone)
        validate_daily_time(default_daily_time)

        if not database_url.startswith("sqlite:///") and not database_url.startswith("postgresql://"):
            raise ValueError("DATABASE_URL must start with sqlite:/// or postgresql://")

        return cls(
            discord_token=token,
            database_url=database_url,
            http_host=http_host,
            http_port=http_port,
            log_level=log_level,
            default_timezone=default_timezone,
            default_daily_time=default_daily_time,
            default_template=default_template,
            retention_days=retention_days,
        )
