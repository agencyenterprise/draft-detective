"""The job queue runs a deferred job on a worker, and only once across workers."""

import asyncio
import json
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from procrastinate import App, PsycopgConnector

from lib.config.env import config
from lib.config.task_queue import DEFAULT_QUEUE, libpq_conninfo, task_queue
from lib.services.task_queue.tasks import ping

WAIT_SECONDS = 20.0
PROBE_SECONDS = 90.0
REPO_ROOT = Path(__file__).resolve().parents[3]
POLL_SECONDS = 0.1
API_WORKERS = 4
JOBS = 40


@pytest.fixture
def job_ids() -> Iterator[list[int]]:
    """The jobs a test defers, deleted (with their events) afterwards."""
    ids: list[int] = []
    yield ids
    with psycopg.connect(libpq_conninfo(config.DATABASE_URL)) as conn:
        conn.execute("DELETE FROM procrastinate_jobs WHERE id = ANY(%s)", (ids,))


async def _wait_until_succeeded(conn: psycopg.AsyncConnection, ids: list[int]) -> None:
    async with asyncio.timeout(WAIT_SECONDS):
        while True:
            cursor = await conn.execute(
                "SELECT count(*) FROM procrastinate_jobs "
                "WHERE id = ANY(%s) AND status = 'succeeded'",
                (ids,),
            )
            row = await cursor.fetchone()
            if row and row[0] == len(ids):
                return
            await asyncio.sleep(POLL_SECONDS)


async def _starts_per_job(conn: psycopg.AsyncConnection, ids: list[int]) -> list[int]:
    cursor = await conn.execute(
        "SELECT count(*) FILTER (WHERE e.type = 'started') FROM procrastinate_jobs j "
        "LEFT JOIN procrastinate_events e ON e.job_id = j.id "
        "WHERE j.id = ANY(%s) GROUP BY j.id",
        (ids,),
    )
    return [row[0] for row in await cursor.fetchall()]


@pytest_asyncio.fixture
async def db() -> AsyncIterator[psycopg.AsyncConnection]:
    conninfo = libpq_conninfo(config.DATABASE_URL)
    async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
        yield conn


async def _is_registered(conn: psycopg.AsyncConnection, worker_id: int) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM procrastinate_workers WHERE id = %s", (worker_id,)
    )
    return await cursor.fetchone() is not None


async def _run_lifespan_probe(message: str) -> dict[str, int]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tests.integration.task_queue.lifespan_probe",
        message,
        cwd=REPO_ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), PROBE_SECONDS)
    assert process.returncode == 0, stderr.decode()[-2000:]
    return json.loads(stdout.decode().strip().splitlines()[-1])


@pytest.mark.asyncio
async def test_the_api_lifespan_runs_deferred_jobs_and_unregisters_on_exit(
    db: psycopg.AsyncConnection, job_ids: list[int]
) -> None:
    ran = await _run_lifespan_probe(f"ping {uuid.uuid4()}")
    job_ids.append(ran["job_id"])

    assert await _starts_per_job(db, job_ids) == [1]
    assert not await _is_registered(db, ran["worker_id"])


def _api_process_queue() -> App:
    """A queue app with its own pool, as each uvicorn worker process has."""
    connector = PsycopgConnector(
        conninfo=libpq_conninfo(config.DATABASE_URL), min_size=1, max_size=4
    )
    return task_queue.with_connector(connector)


async def _run_worker(app: App, name: str) -> None:
    async with app.open_async():
        await app.run_worker_async(
            # Only ping's queue: other tests' jobs are not these workers' to run.
            queues=[DEFAULT_QUEUE],
            concurrency=config.TASK_QUEUE_CONCURRENCY,
            name=name,
            install_signal_handlers=False,
        )


@pytest.mark.asyncio
async def test_several_workers_run_each_job_once(
    db: psycopg.AsyncConnection, job_ids: list[int]
) -> None:
    workers = [
        asyncio.create_task(_run_worker(_api_process_queue(), f"api-{n}"))
        for n in range(API_WORKERS)
    ]
    try:
        async with task_queue.open_async():
            for n in range(JOBS):
                message = f"job {n} {uuid.uuid4()}"
                job_ids.append(await ping.defer_async(message=message))
        await _wait_until_succeeded(db, job_ids)
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    assert await _starts_per_job(db, job_ids) == [1] * JOBS
