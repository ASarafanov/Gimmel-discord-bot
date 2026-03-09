from pathlib import Path

import pytest

from absence_bot.models import (
    GuildSettings,
    LastSeenType,
    MentionMode,
    PostMode,
    TrackMode,
    TrackedUser,
    UserActivity,
)
from absence_bot.storage.sqlite import SqliteStorage
from absence_bot.time_utils import utc_iso


@pytest.mark.asyncio
async def test_sqlite_storage_crud(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStorage(str(db_path))
    await storage.initialize()

    settings = GuildSettings(
        guild_id="1",
        enabled=True,
        report_channel_id="10",
        timezone="UTC",
        daily_time="09:00",
        template_text="test {days}",
        post_mode=PostMode.SINGLE,
        mention_mode=MentionMode.NO_PING,
        track_mode=TrackMode.VOICE_ONLY,
        updated_at_utc=utc_iso(),
    )
    await storage.guild_settings.upsert(settings)

    user = TrackedUser(
        guild_id="1",
        user_id="100",
        display_name="Val",
        enabled=True,
        added_by_user_id="200",
        added_at_utc=utc_iso(),
    )
    await storage.tracked_users.add(user)

    activity = UserActivity(
        guild_id="1",
        user_id="100",
        last_seen_at_utc="2024-01-01T00:00:00+00:00",
        last_seen_type=LastSeenType.VOICE_JOIN,
        last_seen_channel_id="55",
        last_voice_channel_id="55",
        updated_at_utc=utc_iso(),
    )
    await storage.activity.upsert(activity)
    await storage.optout.set("1", "100", True, "test")

    loaded_settings = await storage.guild_settings.get("1")
    assert loaded_settings is not None
    assert loaded_settings.report_channel_id == "10"

    loaded_users = await storage.tracked_users.list_for_guild("1")
    assert len(loaded_users) == 1

    loaded_activity = await storage.activity.get("1", "100")
    assert loaded_activity is not None
    assert loaded_activity.last_seen_channel_id == "55"

    loaded_optout = await storage.optout.get("1", "100")
    assert loaded_optout is not None
    assert loaded_optout.opted_out is True

    await storage.tracked_users.remove("1", "100")
    assert await storage.tracked_users.get("1", "100") is None
    assert await storage.activity.get("1", "100") is None

    await storage.close()
