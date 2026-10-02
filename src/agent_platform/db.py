from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_platform.config import get_settings
from agent_platform.db_url import asyncpg_compatible_url


@lru_cache(maxsize=4)
def _engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        asyncpg_compatible_url(database_url),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )


@lru_cache(maxsize=4)
def session_factory() -> async_sessionmaker[AsyncSession]:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured for database operations.")
    return async_sessionmaker(_engine(database_url), expire_on_commit=False)


async def dispose_engine() -> None:
    database_url = get_settings().database_url
    if database_url:
        await _engine(database_url).dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
