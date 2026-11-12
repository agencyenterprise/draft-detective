"""The Postgres job queue (Procrastinate) and the worker each API process runs.

Every uvicorn worker opens the queue and runs one queue worker from the API
lifespan, so a deploy with `WORKERS=4` has four queue workers. They share one
queue: Postgres hands each job to exactly one of them (`FOR UPDATE SKIP LOCKED`
in `procrastinate_fetch_job_v2`).

The schema comes from an Alembic migration, never from `procrastinate schema
--apply`, so every deploy installs it the way it installs ours.

Connections: the pool (`max_size=4`) fetches, finishes and defers jobs, and
the worker's LISTEN takes one more connection of its own, outside the pool. So
each process adds 5 to the SQLAlchemy engine's 11 and the checkpointer's 4:
80 for a 4-worker deployment, against Postgres's default limit of 100.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from procrastinate import App, PsycopgConnector
from sqlalchemy.engine import make_url

from lib.config.env import config

logger = logging.getLogger(__name__)

# Modules that define tasks. The worker imports them before it fetches a job, so
# a job deferred from any process finds its task.
TASK_MODULES = ["lib.services.task_queue.tasks"]

# How long a stopping worker waits for its running jobs before aborting them.
# Short, so a dev reload or a deploy is not held up; runs cut short here are
# recovered the way a crash is.
SHUTDOWN_GRACEFUL_TIMEOUT_SECONDS = 10.0

# How long a worker that died waits before starting again.
RESTART_DELAY_SECONDS = 5.0


def libpq_conninfo(database_url: str) -> str:
    """The URL as psycopg reads it, without a SQLAlchemy driver suffix."""
    url = make_url(database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


task_queue = App(
    connector=PsycopgConnector(
        conninfo=libpq_conninfo(config.DATABASE_URL), min_size=1, max_size=4
    ),
    import_paths=TASK_MODULES,
)


@asynccontextmanager
async def run_task_queue_worker() -> AsyncIterator[None]:
    """Open the queue and run a worker for as long as the context is open.

    The queue stays open the whole time, so code in this process can defer jobs.
    On exit the worker stops taking jobs and waits up to
    `SHUTDOWN_GRACEFUL_TIMEOUT_SECONDS` for the running ones.
    """

    async with task_queue.open_async():
        worker = asyncio.create_task(_keep_worker_running(), name="task-queue-worker")
        try:
            yield
        finally:
            await _stop_worker(worker)


async def _keep_worker_running() -> None:
    """Run the worker, and start it again whenever it ends, so a process that
    keeps serving requests never silently stops taking jobs.

    Only a cancel stops it (procrastinate re-raises it). The worker runs with
    `wait=True` and nothing else asks it to stop, so returning is as unexpected
    as raising: procrastinate can return after one of its side tasks fails.
    """

    while True:
        try:
            await task_queue.run_worker_async(
                concurrency=config.TASK_QUEUE_CONCURRENCY,
                name=f"api-{os.getpid()}",
                # Uvicorn owns SIGINT and SIGTERM; the lifespan stops the worker.
                install_signal_handlers=False,
                shutdown_graceful_timeout=SHUTDOWN_GRACEFUL_TIMEOUT_SECONDS,
            )
            logger.error(
                "task queue worker stopped; restarting in %ss", RESTART_DELAY_SECONDS
            )
        except Exception:
            logger.exception(
                "task queue worker died; restarting in %ss", RESTART_DELAY_SECONDS
            )
        await asyncio.sleep(RESTART_DELAY_SECONDS)


async def _stop_worker(worker: asyncio.Task[None]) -> None:
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
