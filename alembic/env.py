import os
from logging.config import fileConfig

import alembic_postgresql_enum
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context
from lib.config.env import config as app_config

# Import all models to ensure they are registered with SQLModel.metadata
from lib.models import (
    AppConfig,
    Feedback,
    Issue,
    Project,
    User,
    WorkflowProgress,
    WorkflowRun,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set the database URL from our application config if available
if app_config.DATABASE_URL:
    config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

IGNORE_TABLES = [
    # Ignore LangGraph auto-generated tables
    "checkpoint_writes",
    "checkpoint_blobs",
    "checkpoint_migrations",
    "checkpoints",
    # Ignore LangChain PGVector RAG tables
    "langchain_pg_collection",
    "langchain_pg_embedding",
]


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in IGNORE_TABLES:
        return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
