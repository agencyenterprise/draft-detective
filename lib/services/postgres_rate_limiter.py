"""Postgres-backed rate limiter shared across worker processes.

Drop-in replacement for ``langchain_core.rate_limiters.InMemoryRateLimiter``:
same token bucket semantics, but state lives in a ``rate_limiter_buckets``
row so that every uvicorn worker / pod counts against the same limit.

Concurrency control: each acquire attempt runs one short transaction that
``SELECT ... FOR UPDATE`` s the bucket row, computes the refill, writes the
new state, and commits. The row lock serialises concurrent acquires across
workers; the lock window is a single ``UPDATE``, so contention is bounded.

Fallback policy: fail closed. Any backend error is wrapped in
``RateLimiterBackendError`` and propagated so the awaiting LLM call fails
loudly instead of silently bypassing the limiter.
"""

import asyncio
import logging
import time
from datetime import datetime

from langchain_core.rate_limiters import BaseRateLimiter
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col

from lib.config.database import AsyncSessionLocal
from lib.models.rate_limiter_bucket import RateLimiterBucket

logger = logging.getLogger(__name__)


class RateLimiterBackendError(RuntimeError):
    """Raised when the rate limiter's shared backend is unreachable or errors.

    Propagated (not swallowed) so that callers fail closed rather than
    silently bypassing rate limiting when the shared store misbehaves.
    """


class PostgresRateLimiter(BaseRateLimiter):
    """Token bucket rate limiter backed by a shared Postgres row.

    Parameters mirror ``InMemoryRateLimiter`` so this class is swap-compatible
    from the caller's perspective.

    Args:
        bucket_key: Opaque identifier for the bucket. Callers with the same
            ``bucket_key`` share a single token bucket.
        requests_per_second: Tokens added to the bucket each second.
        check_every_n_seconds: When blocking, how long to sleep between
            consume attempts.
        max_bucket_size: Maximum tokens the bucket can hold (controls burst).
    """

    def __init__(
        self,
        *,
        bucket_key: str,
        requests_per_second: float = 1,
        check_every_n_seconds: float = 0.1,
        max_bucket_size: float = 1,
    ) -> None:
        if max_bucket_size < 1:
            raise ValueError("max_bucket_size must be at least 1")
        self.bucket_key = bucket_key
        self.requests_per_second = requests_per_second
        self.check_every_n_seconds = check_every_n_seconds
        self.max_bucket_size = max_bucket_size

    async def _aconsume(self) -> bool:
        """Attempt a single token consumption. One DB transaction per call.

        Returns True iff a token was consumed. Raises RateLimiterBackendError
        on any backend failure (fail-closed policy).
        """
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Ensure the row exists. A fresh bucket starts full so the
                    # first caller can burst up to max_bucket_size.
                    await session.execute(
                        pg_insert(RateLimiterBucket)
                        .values(
                            bucket_key=self.bucket_key,
                            available_tokens=self.max_bucket_size,
                            last_refill_at=func.now(),
                        )
                        .on_conflict_do_nothing(index_elements=["bucket_key"])
                    )

                    stmt = (
                        select(
                            col(RateLimiterBucket.available_tokens),
                            col(RateLimiterBucket.last_refill_at),
                            func.now(),
                        )
                        .where(col(RateLimiterBucket.bucket_key) == self.bucket_key)
                        .with_for_update()
                    )
                    result = await session.execute(stmt)
                    row = result.one()
                    available_tokens: float = row[0]
                    last_refill_at: datetime = row[1]
                    now_db: datetime = row[2]

                    elapsed = (now_db - last_refill_at).total_seconds()
                    refilled = min(
                        self.max_bucket_size,
                        available_tokens + elapsed * self.requests_per_second,
                    )

                    if refilled >= 1:
                        new_tokens = refilled - 1
                        consumed = True
                    else:
                        # Persist the partial refill so subsequent callers
                        # don't re-count the same elapsed time.
                        new_tokens = refilled
                        consumed = False

                    await session.execute(
                        update(RateLimiterBucket)
                        .where(col(RateLimiterBucket.bucket_key) == self.bucket_key)
                        .values(available_tokens=new_tokens, last_refill_at=now_db)
                    )

                    return consumed
        except RateLimiterBackendError:
            raise
        except Exception as exc:
            logger.error(
                "PostgresRateLimiter backend error for bucket_key=%s: %s",
                self.bucket_key,
                exc,
            )
            raise RateLimiterBackendError(
                f"Rate limiter backend failure for bucket_key={self.bucket_key!r}"
            ) from exc

    def _consume_sync(self) -> bool:
        """Sync fallback: run the async consume on a short-lived event loop.

        Kept simple because the async path (``aacquire``) is what LangChain
        uses in this codebase (all LLM calls go through ``ainvoke``). We
        still provide sync for interface completeness.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are inside a running loop; sync acquire from async
                # contexts is not supported. Callers should use aacquire.
                raise RateLimiterBackendError(
                    "PostgresRateLimiter.acquire() called from a running "
                    "event loop; use aacquire() instead"
                )
        except RuntimeError:
            # No current event loop; fall through to run one.
            pass
        return asyncio.run(self._aconsume())

    def acquire(self, *, blocking: bool = True) -> bool:
        if not blocking:
            return self._consume_sync()
        while not self._consume_sync():
            time.sleep(self.check_every_n_seconds)
        return True

    async def aacquire(self, *, blocking: bool = True) -> bool:
        if not blocking:
            return await self._aconsume()
        while not await self._aconsume():
            await asyncio.sleep(self.check_every_n_seconds)
        return True
