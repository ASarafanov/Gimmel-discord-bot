from __future__ import annotations

from absence_bot.storage.base import Storage


class PostgresStorage(Storage):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def initialize(self) -> None:
        raise NotImplementedError("Postgres storage is not implemented in v1")

    async def close(self) -> None:
        return None
