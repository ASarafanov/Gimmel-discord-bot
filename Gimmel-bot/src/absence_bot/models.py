from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class PostMode(str, Enum):
    SINGLE = "single"
    PER_USER = "per_user"


class MentionMode(str, Enum):
    NO_PING = "no_ping"
    PING = "ping"


class TrackMode(str, Enum):
    VOICE_ONLY = "voice_only"
    MESSAGES = "messages"
    BOTH = "both"


class LastSeenType(str, Enum):
    VOICE_JOIN = "voice_join"
    VOICE_MOVE = "voice_move"
    VOICE_LEAVE = "voice_leave"
    MESSAGE = "message"


@dataclass
class GuildSettings:
    guild_id: str
    enabled: bool
    report_channel_id: Optional[str]
    timezone: str
    daily_time: str
    template_text: str
    post_mode: PostMode
    mention_mode: MentionMode
    track_mode: TrackMode
    updated_at_utc: str


@dataclass
class TrackedUser:
    guild_id: str
    user_id: str
    display_name: Optional[str]
    enabled: bool
    added_by_user_id: Optional[str]
    added_at_utc: str


@dataclass
class UserActivity:
    guild_id: str
    user_id: str
    last_seen_at_utc: Optional[str]
    last_seen_type: Optional[LastSeenType]
    last_seen_channel_id: Optional[str]
    last_voice_channel_id: Optional[str]
    updated_at_utc: str


@dataclass
class UserOptOut:
    guild_id: str
    user_id: str
    opted_out: bool
    opted_out_at_utc: Optional[str]
    reason: Optional[str]


@dataclass
class ReportRow:
    guild_id: str
    user_id: str
    display_name: str
    days_absent: Optional[int]
    last_seen_date: Optional[str]
    last_seen_channel_id: Optional[str]


@dataclass
class RenderedMessage:
    guild_id: str
    channel_id: str
    content: str
    allowed_mentions: dict


@dataclass
class VoiceTransition:
    should_update: bool
    event_type: Optional[LastSeenType]
    new_last_voice_channel_id: Optional[str]
    last_seen_channel_id: Optional[str]


@dataclass
class RuntimeState:
    started_at: datetime
    storage_ready: bool = False
    gateway_ready: bool = False
