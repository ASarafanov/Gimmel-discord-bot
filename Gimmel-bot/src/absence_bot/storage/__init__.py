from absence_bot.storage.base import Storage
from absence_bot.storage.postgres import PostgresStorage
from absence_bot.storage.sqlite import SqliteStorage


def build_storage(database_url: str) -> Storage:
    if database_url.startswith("sqlite:///"):
        return SqliteStorage(database_url.removeprefix("sqlite:///"))
    if database_url.startswith("postgresql://"):
        return PostgresStorage(database_url)
    raise ValueError("Unsupported DATABASE_URL")
