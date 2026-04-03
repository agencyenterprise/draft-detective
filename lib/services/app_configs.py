import logging
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.app_config import AppConfig

logger = logging.getLogger(__name__)


class DefaultConfig(BaseModel):
    """Describes a config key that should exist in the database."""

    key: str
    default_value: str
    description: str


async def get_config(key: str) -> Optional[str]:
    """Return the value for a config key, or None if not set."""
    async with get_async_db_session() as session:
        stmt = select(AppConfig).where(col(AppConfig.key) == key)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.value if row else None


async def get_all_configs() -> List[AppConfig]:
    """Return all config rows, ordered by key."""
    async with get_async_db_session() as session:
        stmt = select(AppConfig).order_by(col(AppConfig.key))
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def upsert_config(
    key: str, value: str, description: Optional[str], user_id: uuid.UUID
) -> AppConfig:
    """Create or update a config row. Returns the saved row."""
    async with get_async_db_session() as session:
        stmt = select(AppConfig).where(col(AppConfig.key) == key)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            row.value = value
            if description is not None:
                row.description = description
            row.updated_by = user_id
            row.updated_at = datetime.utcnow()
        else:
            row = AppConfig(
                key=key,
                value=value,
                description=description or "",
                updated_by=user_id,
            )
            session.add(row)

        await session.commit()
        await session.refresh(row)
        return row


async def delete_config(key: str) -> bool:
    """Delete a config row. Returns True if the row existed."""
    async with get_async_db_session() as session:
        stmt = select(AppConfig).where(col(AppConfig.key) == key)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return False
        await session.delete(row)
        await session.commit()
        return True


async def ensure_defaults(defaults: List[DefaultConfig]) -> None:
    """Ensure every declared config key exists in the database.

    Only inserts missing keys -- never overwrites values that admins
    have already customised.
    """
    async with get_async_db_session() as session:
        stmt = select(col(AppConfig.key))
        result = await session.execute(stmt)
        existing_keys = set(result.scalars().all())

        for cfg in defaults:
            if cfg.key not in existing_keys:
                session.add(
                    AppConfig(
                        key=cfg.key,
                        value=cfg.default_value,
                        description=cfg.description,
                    )
                )
                logger.info("Seeded default config: %s", cfg.key)

        await session.commit()


def _collect_all_defaults() -> List[DefaultConfig]:
    """Gather every DefaultConfig list registered across the codebase."""
    from lib.workflows.about_this_ger.config_keys import ABOUT_THIS_GER_DEFAULTS
    from lib.config_keys.about_page import ABOUT_PAGE_DEFAULTS

    return [*ABOUT_THIS_GER_DEFAULTS, *ABOUT_PAGE_DEFAULTS]


async def seed_all_defaults() -> None:
    """Seed all registered default configs. Safe to call repeatedly."""
    await ensure_defaults(_collect_all_defaults())
