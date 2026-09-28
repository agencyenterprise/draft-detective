"""Durable graph state, for any agent whose thread outlives a single run.

A caller opts in by passing the saver to ``create_deep_agent`` and a ``thread_id`` in the
run config; nothing here knows what a thread belongs to.

Three non-obvious constraints, two of which fail silently:

- **A psycopg pool, not the SQLAlchemy engine.** ``AsyncPostgresSaver`` accepts neither,
  so this is a second pool on the same database.
- **A fresh saver per call over a shared pool.** Each saver holds its own
  ``asyncio.Lock``, so sharing one serialises every concurrent run.
- **Not ``from_conn_string``**, which holds a connection for a whole run.

Both connection pools are configured through environment settings. Budget per process:
DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW + CHECKPOINTER_POOL_MAX_SIZE.
Defaults total 15; four backend processes can therefore use up to 60 connections.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from lib.config.env import config

logger = logging.getLogger(__name__)

# An arbitrary but fixed key, so every worker contends for the same lock. Advisory
# locks live in one tenant-wide namespace, hence something distinctive rather than 1.
SETUP_LOCK_KEY = 0x44445F4341

# The default ``min_size=0`` means an unused process holds nothing; ``prepare_threshold=0`` because a
# transaction-pooling proxy would break on prepared statements; ``autocommit`` and
# ``dict_row`` are required by AsyncPostgresSaver.
checkpointer_pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = (
    AsyncConnectionPool(
        conninfo=config.DATABASE_URL,
        min_size=config.CHECKPOINTER_POOL_MIN_SIZE,
        max_size=config.CHECKPOINTER_POOL_MAX_SIZE,
        timeout=config.CHECKPOINTER_POOL_TIMEOUT,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
    )
)

# Two flags rather than one, because they can disagree: a setup failure leaves the pool
# open but not usable. Conflating them loses track of a pool that shutdown must still
# close, and psycopg_pool refuses to reopen a closed one -- so closing it to recover is
# not an option, and the open flag has to stay honest instead.
_opened = False
_ready = False
_open_lock = asyncio.Lock()


async def _run_setup() -> None:
    """Create the checkpoint tables, once across every worker.

    ``setup()`` is a versioned migration runner and ``checkpoint_migrations.v`` is a
    primary key, so on a fresh database two of the four workers can read the same version
    and race to insert it, one dying on a duplicate key.

    Session-level rather than ``_xact_``, since the pool runs in autocommit and there is
    no transaction to end with -- which makes releasing it our job, or a connection goes
    back to the pool still holding it.
    """

    async with checkpointer_pool.connection() as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (SETUP_LOCK_KEY,))
        try:
            # Idempotent: it reads the applied version first and only applies the rest.
            await AsyncPostgresSaver(conn=conn).setup()
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (SETUP_LOCK_KEY,))


async def _ensure_pool_ready() -> None:
    """Open the pool and run the checkpoint migrations, once per process.

    A failure here leaves the pool open and retries the setup on the next call, which is
    the right answer for the transient kind. It deliberately does not close the pool to
    tidy up: a closed pool cannot be reopened, so that would turn one slow advisory lock
    into every later turn failing.
    """

    global _opened, _ready
    if _ready:
        return
    async with _open_lock:
        # Checked again under the lock: several first calls can arrive together.
        if _ready:
            return
        if not _opened:
            await checkpointer_pool.open(wait=True)
            # Set before setup runs, so a failure there still leaves something to close.
            _opened = True
        await _run_setup()
        _ready = True
        logger.info("checkpointer pool opened and checkpoint tables verified")


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """A saver over the shared pool, opening the pool on first use.

    Yields a new saver each time on purpose -- see the module docstring. The pool is
    what is shared; the saver is a handle with a lock attached.
    """

    await _ensure_pool_ready()
    yield AsyncPostgresSaver(conn=checkpointer_pool)


async def close_checkpointer_pool() -> None:
    """Close the pool, for good. Called from the FastAPI lifespan shutdown.

    One way only: psycopg_pool raises on reopening a closed pool, so this is the end of
    checkpointing in this process rather than something to call between runs.
    """

    global _ready
    if _opened:
        await checkpointer_pool.close()
        # ``_opened`` stays true because the pool remains closed-and-used forever; only
        # readiness is withdrawn, so a later call fails on the pool rather than
        # cheerfully trying to open it again.
        _ready = False
