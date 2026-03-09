from pathlib import Path

import pytest

from absence_bot.models import (
    GuildSettings,
    MentionMode,
    PostMode,
    TrackMode,
    TrackedUser,
    UserActivity,
)
from absence_bot.reporting import RateLimitedError, ReportService
from absence_bot.storage.sqlite import SqliteStorage
from absence_bot.time_utils import utc_iso


class FakeSender:
    def __init__(self, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.attempts = 0
        self.sent: list[dict] = []

    async def send_message(self, channel_id: str, content: str, allowed_mentions: dict) -> None:
        self.attempts += 1
        if self.fail_once and self.attempts == 1:
            raise RateLimitedError(0.01)
        self.sent.append(
            {
                "channel_id": channel_id,
                "content": content,
                "allowed_mentions": allowed_mentions,
            }
        )

    async def close(self) -> None:
        return None


async def _seed_data(storage: SqliteStorage, mention_mode: MentionMode) -> None:
    await storage.guild_settings.upsert(
        GuildSettings(
            guild_id="1",
            enabled=True,
            report_channel_id="10",
            timezone="UTC",
            daily_time="09:00",
            template_text="Прошло {days} {days_word}. Пользователь: {user_mention}",
            post_mode=PostMode.SINGLE,
            mention_mode=mention_mode,
            track_mode=TrackMode.VOICE_ONLY,
            updated_at_utc=utc_iso(),
        )
    )

    await storage.tracked_users.add(
        TrackedUser(
            guild_id="1",
            user_id="100",
            display_name="Val",
            enabled=True,
            added_by_user_id="200",
            added_at_utc=utc_iso(),
        )
    )

    await storage.activity.upsert(
        UserActivity(
            guild_id="1",
            user_id="100",
            last_seen_at_utc="2024-01-01T00:00:00+00:00",
            last_seen_type=None,
            last_seen_channel_id="55",
            last_voice_channel_id="55",
            updated_at_utc=utc_iso(),
        )
    )


@pytest.mark.asyncio
async def test_report_sends_no_ping_by_default(tmp_path: Path) -> None:
    storage = SqliteStorage(str(tmp_path / "report.db"))
    await storage.initialize()
    await _seed_data(storage, MentionMode.NO_PING)

    sender = FakeSender()
    service = ReportService(storage, sender, default_template="x", max_send_retries=2)

    sent_count = await service.publish_guild_report("1")

    assert sent_count == 1
    assert len(sender.sent) == 1
    assert sender.sent[0]["allowed_mentions"] == {"parse": []}
    assert len(sender.sent[0]["content"]) <= 2000

    await storage.close()


@pytest.mark.asyncio
async def test_report_retries_on_rate_limit(tmp_path: Path) -> None:
    storage = SqliteStorage(str(tmp_path / "retry.db"))
    await storage.initialize()
    await _seed_data(storage, MentionMode.PING)

    sender = FakeSender(fail_once=True)
    service = ReportService(storage, sender, default_template="x", max_send_retries=2)

    sent_count = await service.publish_guild_report("1")

    assert sent_count == 1
    assert sender.attempts == 2
    assert sender.sent[0]["allowed_mentions"]["users"] == ["100"]

    await storage.close()
