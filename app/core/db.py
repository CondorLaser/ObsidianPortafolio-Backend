import ssl
from collections.abc import AsyncIterator

import certifi
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()


def _build_connect_args(database_url: str) -> dict:
    if "neon.tech" not in database_url:
        return {}
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    return {"ssl": ssl_ctx}


_db_url = settings.database_url

engine = create_async_engine(
    _db_url,
    pool_pre_ping=True,
    future=True,
    connect_args=_build_connect_args(_db_url),
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
