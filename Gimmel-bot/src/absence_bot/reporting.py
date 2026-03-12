from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Protocol

import aiohttp

from absence_bot.models import (
    GuildSettings,
    MentionMode,
    RenderedMessage,
    ReportRow,
    TrackedUser,
    UserActivity,
)
from absence_bot.templates import chunk_lines, render_user_line
from absence_bot.time_utils import calculate_absence_days, format_local_date, now_utc, utc_iso
from absence_bot.voice_logic import classify_voice_transition


class RateLimitedError(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limited, retry after {retry_after}s")
        self.retry_after = max(retry_after, 0.1)


class DiscordApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Discord API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message

    @property
    def is_transient(self) -> bool:
        return self.status_code >= 500


class MessageSender(Protocol):
    async def send_message(self, channel_id: str, content: str, allowed_mentions: dict) -> None:
        ...

    async def close(self) -> None:
        ...


class DiscordHttpMessageSender:
    def __init__(self, bot_token: str, base_url: str = "https://discord.com/api/v10") -> None:
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _session_or_create(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bot {self._bot_token}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def send_message(self, channel_id: str, content: str, allowed_mentions: dict) -> None:
        session = await self._session_or_create()
        payload = {"content": content, "allowed_mentions": allowed_mentions}
        url = f"{self._base_url}/channels/{channel_id}/messages"

        async with session.post(url, json=payload) as response:
            if response.status == 429:
                body = await response.json(content_type=None)
                retry_after = _extract_retry_after(response.headers, body)
                raise RateLimitedError(retry_after)

            if response.status >= 400:
                text = await response.text()
                raise DiscordApiError(response.status, text)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


@dataclass
class UserSnapshot:
    tracked: TrackedUser
    activity: Optional[UserActivity]
    days_absent: Optional[int]
    last_seen_date: Optional[str]


class ReportService:
    def __init__(
        self,
        storage,
        sender: MessageSender,
        default_template: str,
        max_send_retries: int,
    ) -> None:
        self._storage = storage
        self._sender = sender
        self._default_template = default_template
        self._max_send_retries = max_send_retries
        self._logger = logging.getLogger("absence_bot.reporting")

    async def handle_voice_state_update(
        self,
        guild_id: str,
        user_id: str,
        before_channel_id: Optional[str],
        after_channel_id: Optional[str],
        display_name: Optional[str],
    ) -> None:
        tracked = await self._storage.tracked_users.get(guild_id, user_id)
        if tracked is None or not tracked.enabled:
            return

        optout = await self._storage.optout.get(guild_id, user_id)
        if optout is not None and optout.opted_out:
            return

        if display_name:
            await self._storage.tracked_users.set_display_name(guild_id, user_id, display_name)

        transition = classify_voice_transition(before_channel_id, after_channel_id)
        current_activity = await self._storage.activity.get(guild_id, user_id)

        if current_activity is None:
            current_activity = UserActivity(
                guild_id=guild_id,
                user_id=user_id,
                last_seen_at_utc=None,
                last_seen_type=None,
                last_seen_channel_id=None,
                last_voice_channel_id=None,
                updated_at_utc=utc_iso(),
            )

        if transition.should_update:
            current_activity.last_seen_at_utc = utc_iso()
            current_activity.last_seen_type = transition.event_type
            current_activity.last_seen_channel_id = transition.last_seen_channel_id

        current_activity.last_voice_channel_id = transition.new_last_voice_channel_id
        current_activity.updated_at_utc = utc_iso()

        await self._storage.activity.upsert(current_activity)

    async def build_rows(self, guild_id: str, at_utc: Optional[datetime] = None) -> List[ReportRow]:
        report_time = at_utc or now_utc()
        settings = await self._storage.guild_settings.get(guild_id)
        if settings is None:
            return []

        users = await self._storage.tracked_users.list_for_guild(guild_id)
        rows: List[ReportRow] = []

        for user in users:
            optout = await self._storage.optout.get(guild_id, user.user_id)
            if optout is not None and optout.opted_out:
                continue

            activity = await self._storage.activity.get(guild_id, user.user_id)
            days_absent: Optional[int] = None
            last_seen_date: Optional[str] = None
            last_seen_channel_id: Optional[str] = None

            if activity and activity.last_seen_at_utc:
                days_absent = calculate_absence_days(activity.last_seen_at_utc, report_time, settings.timezone)
                last_seen_date = format_local_date(activity.last_seen_at_utc, settings.timezone)
                last_seen_channel_id = activity.last_seen_channel_id

            rows.append(
                ReportRow(
                    guild_id=guild_id,
                    user_id=user.user_id,
                    display_name=user.display_name or f"User {user.user_id}",
                    days_absent=days_absent,
                    last_seen_date=last_seen_date,
                    last_seen_channel_id=last_seen_channel_id,
                )
            )

        return rows

    async def build_messages(self, guild_id: str, at_utc: Optional[datetime] = None) -> List[RenderedMessage]:
        settings = await self._storage.guild_settings.get(guild_id)
        if settings is None or not settings.enabled or not settings.report_channel_id:
            return []

        rows = await self.build_rows(guild_id, at_utc)
        if not rows:
            return []

        template = settings.template_text or self._default_template
        lines: List[str] = []
        user_ids: List[str] = []

        for row in rows:
            line = render_user_line(
                template,
                days=row.days_absent,
                display_name=row.display_name,
                user_id=row.user_id,
                user_mention=f"<@{row.user_id}>",
                last_seen_date=row.last_seen_date,
                last_seen_channel_id=row.last_seen_channel_id,
            )
            lines.append(line)
            user_ids.append(row.user_id)

        allowed_mentions = self._build_allowed_mentions(settings, user_ids)

        if settings.post_mode.value == "per_user":
            return [
                RenderedMessage(
                    guild_id=guild_id,
                    channel_id=settings.report_channel_id,
                    content=line[:2000],
                    allowed_mentions=allowed_mentions,
                )
                for line in lines
            ]

        chunks = chunk_lines(lines, max_len=2000)
        return [
            RenderedMessage(
                guild_id=guild_id,
                channel_id=settings.report_channel_id,
                content=chunk,
                allowed_mentions=allowed_mentions,
            )
            for chunk in chunks
        ]

    async def publish_guild_report(self, guild_id: str, at_utc: Optional[datetime] = None) -> int:
        messages = await self.build_messages(guild_id, at_utc)
        sent = 0
        for message in messages:
            await self._send_with_retry(message)
            sent += 1

        self._logger.info("daily report sent", extra={"guild_id": guild_id, "messages": sent})
        return sent

    async def publish_all(self) -> int:
        sent_total = 0
        for settings in await self._storage.guild_settings.list_all():
            if not settings.enabled:
                continue
            sent_total += await self.publish_guild_report(settings.guild_id)
        return sent_total

    async def _send_with_retry(self, message: RenderedMessage) -> None:
        for attempt in range(self._max_send_retries + 1):
            try:
                await self._sender.send_message(
                    message.channel_id,
                    message.content,
                    message.allowed_mentions,
                )
                return
            except RateLimitedError as exc:
                if attempt >= self._max_send_retries:
                    raise
                await asyncio.sleep(exc.retry_after)
            except DiscordApiError as exc:
                if attempt >= self._max_send_retries or not exc.is_transient:
                    raise
                await asyncio.sleep(min(2**attempt, 10))

    def _build_allowed_mentions(self, settings: GuildSettings, user_ids: List[str]) -> dict:
        if settings.mention_mode == MentionMode.NO_PING:
            return {"parse": []}
        return {"users": user_ids, "parse": []}


def _extract_retry_after(headers: aiohttp.typedefs.LooseHeaders, body: object) -> float:
    if isinstance(body, dict) and "retry_after" in body:
        try:
            return float(body["retry_after"])
        except (TypeError, ValueError):
            pass

    header_value = None
    if isinstance(headers, dict):
        header_value = headers.get("Retry-After")
    else:
        header_value = headers.get("Retry-After")

    if header_value:
        try:
            return float(header_value)
        except ValueError:
            return 1.0

    return 1.0
