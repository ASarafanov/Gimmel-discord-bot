from pathlib import Path

import pytest

from absence_bot.models import GuildSettings, MentionMode, PostMode, TrackMode, TrackedUser
from absence_bot.reporting import ReportService
from absence_bot.storage.sqlite import SqliteStorage
from absence_bot.time_utils import utc_iso


class DummySender:
    async def send_message(self, channel_id: str, content: str, allowed_mentions: dict) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_handle_voice_state_updates_only_on_leave(tmp_path: Path) -> None:
    storage = SqliteStorage(str(tmp_path / "voice.db"))
    await storage.initialize()

    await storage.guild_settings.upsert(
        GuildSettings(
            guild_id="1",
            enabled=True,
            report_channel_id="10",
            timezone="UTC",
            daily_time="09:00",
            template_text="x",
            post_mode=PostMode.SINGLE,
            mention_mode=MentionMode.NO_PING,
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

    service = ReportService(storage, DummySender(), default_template="x", max_send_retries=1)

    await service.handle_voice_state_update("1", "100", None, "c1", "Val")
    activity_1 = await storage.activity.get("1", "100")
    assert activity_1 is not None
    assert activity_1.last_seen_channel_id is None
    first_seen = activity_1.last_seen_at_utc
    assert first_seen is None

    await service.handle_voice_state_update("1", "100", "c1", "c1", "Val")
    activity_2 = await storage.activity.get("1", "100")
    assert activity_2 is not None
    assert activity_2.last_seen_at_utc == first_seen

    await service.handle_voice_state_update("1", "100", "c1", "c2", "Val")
    activity_3 = await storage.activity.get("1", "100")
    assert activity_3 is not None
    assert activity_3.last_seen_channel_id is None
    assert activity_3.last_seen_type is None

    await service.handle_voice_state_update("1", "100", "c2", None, "Val")
    activity_4 = await storage.activity.get("1", "100")
    assert activity_4 is not None
    assert activity_4.last_seen_channel_id == "c2"
    assert activity_4.last_seen_type is not None
    assert activity_4.last_seen_type.value == "voice_leave"
    assert activity_4.last_seen_at_utc is not None

    await storage.close()
