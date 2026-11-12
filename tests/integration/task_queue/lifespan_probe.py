"""Run `lib.api.main`'s lifespan in a fresh interpreter and defer one job.

The integration test runs this as a child process: the MCP unit tests swap the
auth factory at import, so `lib.api.main` can't be imported in the test process
itself. Prints the job's id and the worker that ran it, as JSON, once the
lifespan has exited.
"""

import asyncio
import json
import sys

import psycopg

from lib.api import main as api_main
from lib.config.env import config
from lib.config.task_queue import libpq_conninfo
from lib.services.task_queue.tasks import ping

WAIT_SECONDS = 20.0


async def _idle(*_: float, **__: float) -> None:
    await asyncio.Event().wait()


async def _worker_once_succeeded(conn: psycopg.AsyncConnection, job_id: int) -> int:
    async with asyncio.timeout(WAIT_SECONDS):
        while True:
            cursor = await conn.execute(
                "SELECT worker_id FROM procrastinate_jobs "
                "WHERE id = %s AND status = 'succeeded'",
                (job_id,),
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
            await asyncio.sleep(0.1)


async def main() -> None:
    # The reaper would sweep other tests' rows: only the queue worker runs.
    api_main.run_reaper_loop = _idle
    conninfo = libpq_conninfo(config.DATABASE_URL)
    async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
        async with api_main.lifespan(api_main.app):
            job_id = await ping.defer_async(message=sys.argv[1])
            worker_id = await _worker_once_succeeded(conn, job_id)
    print(json.dumps({"job_id": job_id, "worker_id": worker_id}))


if __name__ == "__main__":
    asyncio.run(main())
