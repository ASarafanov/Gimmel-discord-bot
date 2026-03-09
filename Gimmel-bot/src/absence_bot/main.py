from __future__ import annotations

import asyncio
import logging

from absence_bot import __version__
from absence_bot.commands import AbsenceCommandRegistrar
from absence_bot.config import Settings
from absence_bot.discord_bot import AbsenceBot
from absence_bot.http_server import HealthServer
from absence_bot.logging_utils import setup_logging
from absence_bot.models import RuntimeState
from absence_bot.reporting import DiscordHttpMessageSender, ReportService
from absence_bot.scheduler import ReportScheduler
from absence_bot.storage import build_storage
from absence_bot.time_utils import now_utc


async def run() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    logger = logging.getLogger("absence_bot.main")

    runtime_state = RuntimeState(started_at=now_utc())

    storage = build_storage(settings.database_url)
    await storage.initialize()
    runtime_state.storage_ready = True

    sender = DiscordHttpMessageSender(settings.discord_token)
    report_service = ReportService(
        storage=storage,
        sender=sender,
        default_template=settings.default_template,
        max_send_retries=settings.max_send_retries,
    )
    scheduler = ReportScheduler(storage=storage, report_service=report_service)

    registrar = AbsenceCommandRegistrar(
        storage=storage,
        report_service=report_service,
        scheduler=scheduler,
        default_timezone=settings.default_timezone,
        default_daily_time=settings.default_daily_time,
        default_template=settings.default_template,
        retention_days=settings.retention_days,
    )

    bot = AbsenceBot(
        command_registrar=registrar,
        report_service=report_service,
        scheduler=scheduler,
        runtime_state=runtime_state,
    )

    health_server = HealthServer(
        host=settings.http_host,
        port=settings.http_port,
        version=__version__,
        readiness_check=lambda: runtime_state.storage_ready and runtime_state.gateway_ready,
    )

    await health_server.start()
    logger.info("health server started")

    try:
        await bot.start(settings.discord_token)
    finally:
        await health_server.stop()
        await sender.close()
        await storage.close()
        runtime_state.storage_ready = False


if __name__ == "__main__":
    asyncio.run(run())
