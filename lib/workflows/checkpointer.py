import asyncio
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from lib.config.env import config

# psycopg pool for langgraph's AsyncPostgresSaver. Opened lazily by
# _ensure_pool_ready(); min_size=0 so idle processes hold no DB connections.
checkpointer_pool = AsyncConnectionPool(
    conninfo=config.DATABASE_URL,
    min_size=0,
    max_size=4,
    kwargs={
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    },
    open=False,
)

_opened = False
_open_lock = asyncio.Lock()


async def _ensure_pool_ready() -> None:
    """Open the shared psycopg pool and run checkpoint migrations once."""
    global _opened
    if _opened:
        return
    async with _open_lock:
        if _opened:
            return
        await checkpointer_pool.open(wait=True)
        # Idempotent; creates checkpoint tables on first startup.
        await AsyncPostgresSaver(conn=checkpointer_pool).setup()
        _opened = True


@asynccontextmanager
async def get_checkpointer():
    """Yield an AsyncPostgresSaver backed by the shared psycopg pool.

    A fresh saver is created per call (it's cheap — just assigns attrs and
    creates an asyncio.Lock). All savers share ``checkpointer_pool`` so the
    per-process connection count stays bounded, while each saver has its own
    lock so concurrent workflow runs don't serialize on a global checkpoint
    lock.
    """
    await _ensure_pool_ready()
    yield AsyncPostgresSaver(conn=checkpointer_pool)


async def close_checkpointer_pool() -> None:
    """Close the shared pool; called from the FastAPI lifespan shutdown hook."""
    global _opened
    if _opened:
        await checkpointer_pool.close()
        _opened = False
