from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from lib.config.env import config as env_config


def get_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# SQLAlchemy engine
async_engine = create_async_engine(get_async_url(env_config.DATABASE_URL), echo=False)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)

# Base class for models
Base = declarative_base()


@asynccontextmanager
async def get_async_db_session():
    """
    Dependency to get async database session.

    Note: Callers are responsible for calling `await session.commit()`
    to persist changes. Rollback is automatic on exception.
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
