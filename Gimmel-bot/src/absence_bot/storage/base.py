from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from absence_bot.models import GuildSettings, TrackedUser, UserActivity, UserOptOut


class GuildSettingsRepo(ABC):
    @abstractmethod
    async def get(self, guild_id: str) -> Optional[GuildSettings]:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> List[GuildSettings]:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, settings: GuildSettings) -> None:
        raise NotImplementedError


class TrackedUsersRepo(ABC):
    @abstractmethod
    async def add(self, tracked_user: TrackedUser) -> None:
        raise NotImplementedError

    @abstractmethod
    async def remove(self, guild_id: str, user_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, guild_id: str, user_id: str) -> Optional[TrackedUser]:
        raise NotImplementedError

    @abstractmethod
    async def list_for_guild(self, guild_id: str, enabled_only: bool = True) -> List[TrackedUser]:
        raise NotImplementedError

    @abstractmethod
    async def set_display_name(self, guild_id: str, user_id: str, display_name: str) -> None:
        raise NotImplementedError


class ActivityRepo(ABC):
    @abstractmethod
    async def get(self, guild_id: str, user_id: str) -> Optional[UserActivity]:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, activity: UserActivity) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_for_guild(self, guild_id: str) -> List[UserActivity]:
        raise NotImplementedError


class OptOutRepo(ABC):
    @abstractmethod
    async def get(self, guild_id: str, user_id: str) -> Optional[UserOptOut]:
        raise NotImplementedError

    @abstractmethod
    async def set(self, guild_id: str, user_id: str, opted_out: bool, reason: Optional[str]) -> None:
        raise NotImplementedError


class Storage(ABC):
    guild_settings: GuildSettingsRepo
    tracked_users: TrackedUsersRepo
    activity: ActivityRepo
    optout: OptOutRepo

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
