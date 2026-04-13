"""Integration tests for the Postgres-backed rate limiter.

These tests hit a real Postgres (same DATABASE_URL used by the rest of the
test suite). They verify:

1. Cross-instance state sharing — separate PostgresRateLimiter objects
   pointing at the same bucket_key count against the same bucket. This is
   the regression guard the old in-memory limiter would fail.
2. Fail-closed behaviour on backend errors.
"""

import asyncio
import time
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.rate_limiter_bucket import RateLimiterBucket
from lib.services.postgres_rate_limiter import (
    PostgresRateLimiter,
    RateLimiterBackendError,
)


@pytest_asyncio.fixture
async def bucket_key():
    """Unique bucket_key per test so parallel runs don't interfere."""
    key = f"test-{uuid.uuid4().hex[:12]}"
    yield key

    # Cleanup
    async with get_async_db_session() as session:
        await session.execute(
            delete(RateLimiterBucket).where(col(RateLimiterBucket.bucket_key) == key)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_cross_instance_state_is_shared(bucket_key):
    """N separate limiter instances with the same bucket_key share one bucket.

    This is the core regression guard: the old InMemoryRateLimiter would
    allow N * max_bucket_size acquires in this same setup.
    """
    rps = 10.0
    max_bucket = 10.0
    num_instances = 4
    duration_seconds = 2.0

    # Each "worker" gets its own limiter instance (fresh in-memory state).
    limiters = [
        PostgresRateLimiter(
            bucket_key=bucket_key,
            requests_per_second=rps,
            check_every_n_seconds=0.05,
            max_bucket_size=max_bucket,
        )
        for _ in range(num_instances)
    ]

    acquires_per_worker = [0] * num_instances
    stop_at = time.monotonic() + duration_seconds

    async def worker(idx: int):
        while time.monotonic() < stop_at:
            ok = await limiters[idx].aacquire(blocking=False)
            if ok:
                acquires_per_worker[idx] += 1
            else:
                await asyncio.sleep(0.01)

    await asyncio.gather(*(worker(i) for i in range(num_instances)))

    total = sum(acquires_per_worker)
    # Budget: initial burst + refill over the window, with jitter allowance.
    expected_max = max_bucket + rps * duration_seconds
    # Allow +50% jitter for refill timing / scheduler slack, but crucially
    # the old per-worker limiter would produce ~ num_instances * expected_max
    # (~4x) which this bound rules out.
    assert total <= int(expected_max * 1.5), (
        f"Shared bucket allowed {total} acquires, expected <= "
        f"{int(expected_max * 1.5)} (per-worker counts: {acquires_per_worker})"
    )
    # Sanity: we did get meaningful throughput (not zero).
    assert total >= int(max_bucket), (
        f"Shared bucket only allowed {total} acquires; expected at least "
        f"{int(max_bucket)} from the initial burst"
    )


@pytest.mark.asyncio
async def test_non_blocking_acquire_returns_false_when_empty(bucket_key):
    """Once the initial burst is drained, non-blocking acquires return False."""
    limiter = PostgresRateLimiter(
        bucket_key=bucket_key,
        requests_per_second=0.01,  # essentially no refill during this test
        check_every_n_seconds=0.05,
        max_bucket_size=2,
    )

    # Drain the bucket.
    assert await limiter.aacquire(blocking=False) is True
    assert await limiter.aacquire(blocking=False) is True
    # Next call: bucket is empty and refill rate is negligible.
    assert await limiter.aacquire(blocking=False) is False


@pytest.mark.asyncio
async def test_fail_closed_on_backend_error(monkeypatch):
    """If the DB layer raises, RateLimiterBackendError propagates."""
    limiter = PostgresRateLimiter(
        bucket_key="never-persisted",
        requests_per_second=1,
        max_bucket_size=1,
    )

    class _BrokenSessionFactory:
        def __call__(self):
            raise OSError("simulated DB outage")

    monkeypatch.setattr(
        "lib.services.postgres_rate_limiter.AsyncSessionLocal",
        _BrokenSessionFactory(),
    )

    with pytest.raises(RateLimiterBackendError):
        await limiter.aacquire(blocking=False)
