from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


class ReportScheduler:
    def __init__(self, storage, report_service) -> None:
        self._storage = storage
        self._report_service = report_service
        self._scheduler = AsyncIOScheduler()
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("absence_bot.scheduler")

    async def start(self) -> None:
        self._scheduler.start()
        await self.reload_jobs()

    async def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def reload_jobs(self) -> None:
        async with self._lock:
            for job in self._scheduler.get_jobs():
                self._scheduler.remove_job(job.id)

            for settings in await self._storage.guild_settings.list_all():
                if not settings.enabled or not settings.report_channel_id:
                    continue

                hour, minute = _parse_daily_time(settings.daily_time)
                job_id = f"daily_report_{settings.guild_id}"
                self._scheduler.add_job(
                    self._run_guild,
                    trigger=CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone=settings.timezone,
                    ),
                    id=job_id,
                    replace_existing=True,
                    args=[settings.guild_id],
                    coalesce=True,
                    misfire_grace_time=300,
                )

                self._logger.info(
                    "scheduled guild report",
                    extra={
                        "guild_id": settings.guild_id,
                        "daily_time": settings.daily_time,
                        "timezone": settings.timezone,
                    },
                )

    async def run_now(self, guild_id: str) -> int:
        return await self._report_service.publish_guild_report(guild_id)

    async def _run_guild(self, guild_id: str) -> None:
        try:
            await self._report_service.publish_guild_report(guild_id)
        except Exception:
            self._logger.exception("scheduled report failed", extra={"guild_id": guild_id})


def _parse_daily_time(value: str) -> tuple[int, int]:
    hour_str, minute_str = value.split(":")
    return int(hour_str), int(minute_str)
