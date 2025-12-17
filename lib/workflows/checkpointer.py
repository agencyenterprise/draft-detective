from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from lib.config.env import config


@asynccontextmanager
async def get_checkpointer():
    async with AsyncPostgresSaver.from_conn_string(config.DATABASE_URL) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
