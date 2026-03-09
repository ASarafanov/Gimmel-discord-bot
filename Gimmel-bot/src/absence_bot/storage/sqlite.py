from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import aiosqlite

from absence_bot.models import (
    GuildSettings,
    LastSeenType,
    MentionMode,
    PostMode,
    TrackMode,
    TrackedUser,
    UserActivity,
    UserOptOut,
)
from absence_bot.storage.base import ActivityRepo, GuildSettingsRepo, OptOutRepo, Storage, TrackedUsersRepo
from absence_bot.time_utils import utc_iso


class SqliteGuildSettingsRepo(GuildSettingsRepo):
    def __init__(self, conn: aiosqlite.Connection, lock: asyncio.Lock) -> None:
        self._conn = conn
        self._lock = lock

    async def get(self, guild_id: str) -> Optional[GuildSettings]:
        row = await _fetchone(
            self._conn,
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
        return _guild_settings_from_row(row)

    async def list_all(self) -> List[GuildSettings]:
        rows = await _fetchall(self._conn, "SELECT * FROM guild_settings ORDER BY guild_id")
        return [_guild_settings_from_row(row) for row in rows if row is not None]

    async def upsert(self, settings: GuildSettings) -> None:
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO guild_settings (
                  guild_id, enabled, report_channel_id, timezone, daily_time,
                  template_text, post_mode, mention_mode, track_mode, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                  enabled = excluded.enabled,
                  report_channel_id = excluded.report_channel_id,
                  timezone = excluded.timezone,
                  daily_time = excluded.daily_time,
                  template_text = excluded.template_text,
                  post_mode = excluded.post_mode,
                  mention_mode = excluded.mention_mode,
                  track_mode = excluded.track_mode,
                  updated_at_utc = excluded.updated_at_utc
                """,
                (
                    settings.guild_id,
                    1 if settings.enabled else 0,
                    settings.report_channel_id,
                    settings.timezone,
                    settings.daily_time,
                    settings.template_text,
                    settings.post_mode.value,
                    settings.mention_mode.value,
                    settings.track_mode.value,
                    settings.updated_at_utc,
                ),
            )
            await self._conn.commit()


class SqliteTrackedUsersRepo(TrackedUsersRepo):
    def __init__(self, conn: aiosqlite.Connection, lock: asyncio.Lock) -> None:
        self._conn = conn
        self._lock = lock

    async def add(self, tracked_user: TrackedUser) -> None:
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO tracked_users (
                  guild_id, user_id, display_name, enabled, added_by_user_id, added_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                  display_name = excluded.display_name,
                  enabled = excluded.enabled
                """,
                (
                    tracked_user.guild_id,
                    tracked_user.user_id,
                    tracked_user.display_name,
                    1 if tracked_user.enabled else 0,
                    tracked_user.added_by_user_id,
                    tracked_user.added_at_utc,
                ),
            )
            await self._conn.commit()

    async def remove(self, guild_id: str, user_id: str) -> None:
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM tracked_users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self._conn.commit()

    async def get(self, guild_id: str, user_id: str) -> Optional[TrackedUser]:
        row = await _fetchone(
            self._conn,
            "SELECT * FROM tracked_users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return _tracked_user_from_row(row)

    async def list_for_guild(self, guild_id: str, enabled_only: bool = True) -> List[TrackedUser]:
        query = "SELECT * FROM tracked_users WHERE guild_id = ?"
        params = [guild_id]
        if enabled_only:
            query += " AND enabled = 1"
        query += " ORDER BY added_at_utc"

        rows = await _fetchall(self._conn, query, tuple(params))
        return [_tracked_user_from_row(row) for row in rows if row is not None]

    async def set_display_name(self, guild_id: str, user_id: str, display_name: str) -> None:
        async with self._lock:
            await self._conn.execute(
                "UPDATE tracked_users SET display_name = ? WHERE guild_id = ? AND user_id = ?",
                (display_name, guild_id, user_id),
            )
            await self._conn.commit()


class SqliteActivityRepo(ActivityRepo):
    def __init__(self, conn: aiosqlite.Connection, lock: asyncio.Lock) -> None:
        self._conn = conn
        self._lock = lock

    async def get(self, guild_id: str, user_id: str) -> Optional[UserActivity]:
        row = await _fetchone(
            self._conn,
            "SELECT * FROM user_activity WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return _activity_from_row(row)

    async def upsert(self, activity: UserActivity) -> None:
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO user_activity (
                  guild_id, user_id, last_seen_at_utc, last_seen_type,
                  last_seen_channel_id, last_voice_channel_id, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                  last_seen_at_utc = excluded.last_seen_at_utc,
                  last_seen_type = excluded.last_seen_type,
                  last_seen_channel_id = excluded.last_seen_channel_id,
                  last_voice_channel_id = excluded.last_voice_channel_id,
                  updated_at_utc = excluded.updated_at_utc
                """,
                (
                    activity.guild_id,
                    activity.user_id,
                    activity.last_seen_at_utc,
                    activity.last_seen_type.value if activity.last_seen_type else None,
                    activity.last_seen_channel_id,
                    activity.last_voice_channel_id,
                    activity.updated_at_utc,
                ),
            )
            await self._conn.commit()

    async def list_for_guild(self, guild_id: str) -> List[UserActivity]:
        rows = await _fetchall(
            self._conn,
            "SELECT * FROM user_activity WHERE guild_id = ?",
            (guild_id,),
        )
        return [_activity_from_row(row) for row in rows if row is not None]


class SqliteOptOutRepo(OptOutRepo):
    def __init__(self, conn: aiosqlite.Connection, lock: asyncio.Lock) -> None:
        self._conn = conn
        self._lock = lock

    async def get(self, guild_id: str, user_id: str) -> Optional[UserOptOut]:
        row = await _fetchone(
            self._conn,
            "SELECT * FROM user_optout WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return _optout_from_row(row)

    async def set(self, guild_id: str, user_id: str, opted_out: bool, reason: Optional[str]) -> None:
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO user_optout (guild_id, user_id, opted_out, opted_out_at_utc, reason)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                  opted_out = excluded.opted_out,
                  opted_out_at_utc = excluded.opted_out_at_utc,
                  reason = excluded.reason
                """,
                (
                    guild_id,
                    user_id,
                    1 if opted_out else 0,
                    utc_iso() if opted_out else None,
                    reason,
                ),
            )
            await self._conn.commit()


class SqliteStorage(Storage):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self.guild_settings: GuildSettingsRepo
        self.tracked_users: TrackedUsersRepo
        self.activity: ActivityRepo
        self.optout: OptOutRepo

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")

        schema_path = Path(__file__).with_name("schema.sql")
        await self._conn.executescript(schema_path.read_text(encoding="utf-8"))
        await self._conn.commit()

        self.guild_settings = SqliteGuildSettingsRepo(self._conn, self._lock)
        self.tracked_users = SqliteTrackedUsersRepo(self._conn, self._lock)
        self.activity = SqliteActivityRepo(self._conn, self._lock)
        self.optout = SqliteOptOutRepo(self._conn, self._lock)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


def _guild_settings_from_row(row: Optional[aiosqlite.Row]) -> Optional[GuildSettings]:
    if row is None:
        return None
    return GuildSettings(
        guild_id=row["guild_id"],
        enabled=bool(row["enabled"]),
        report_channel_id=row["report_channel_id"],
        timezone=row["timezone"],
        daily_time=row["daily_time"],
        template_text=row["template_text"],
        post_mode=PostMode(row["post_mode"]),
        mention_mode=MentionMode(row["mention_mode"]),
        track_mode=TrackMode(row["track_mode"]),
        updated_at_utc=row["updated_at_utc"],
    )


def _tracked_user_from_row(row: Optional[aiosqlite.Row]) -> Optional[TrackedUser]:
    if row is None:
        return None
    return TrackedUser(
        guild_id=row["guild_id"],
        user_id=row["user_id"],
        display_name=row["display_name"],
        enabled=bool(row["enabled"]),
        added_by_user_id=row["added_by_user_id"],
        added_at_utc=row["added_at_utc"],
    )


def _activity_from_row(row: Optional[aiosqlite.Row]) -> Optional[UserActivity]:
    if row is None:
        return None
    last_seen_type = row["last_seen_type"]
    return UserActivity(
        guild_id=row["guild_id"],
        user_id=row["user_id"],
        last_seen_at_utc=row["last_seen_at_utc"],
        last_seen_type=LastSeenType(last_seen_type) if last_seen_type else None,
        last_seen_channel_id=row["last_seen_channel_id"],
        last_voice_channel_id=row["last_voice_channel_id"],
        updated_at_utc=row["updated_at_utc"],
    )


def _optout_from_row(row: Optional[aiosqlite.Row]) -> Optional[UserOptOut]:
    if row is None:
        return None
    return UserOptOut(
        guild_id=row["guild_id"],
        user_id=row["user_id"],
        opted_out=bool(row["opted_out"]),
        opted_out_at_utc=row["opted_out_at_utc"],
        reason=row["reason"],
    )


async def _fetchone(
    conn: aiosqlite.Connection,
    query: str,
    params: tuple,
) -> Optional[aiosqlite.Row]:
    cursor = await conn.execute(query, params)
    try:
        return await cursor.fetchone()
    finally:
        await cursor.close()


async def _fetchall(
    conn: aiosqlite.Connection,
    query: str,
    params: tuple = (),
) -> List[aiosqlite.Row]:
    cursor = await conn.execute(query, params)
    try:
        return await cursor.fetchall()
    finally:
        await cursor.close()
