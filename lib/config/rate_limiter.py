import hashlib
from functools import lru_cache

from lib.config.env import config as env_config
from lib.services.postgres_rate_limiter import PostgresRateLimiter


def hash_api_key(api_key: str) -> str:
    """Return a short hash of an API key suitable for use as a rate-limiter key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


@lru_cache(maxsize=256)
def get_rate_limiter(bucket_key: str) -> PostgresRateLimiter:
    """Return the shared (Postgres-backed) rate limiter for ``bucket_key``.

    The limiter instance itself is cached per-key (cheap, stateless wrapper);
    the actual token bucket state lives in the ``rate_limiter_buckets`` table
    so the limit applies globally across all workers.

    Tuning knobs come from env vars (see ``lib/config/env.py``):
    ``RATE_LIMITER_REQUESTS_PER_SECOND``, ``RATE_LIMITER_MAX_BUCKET_SIZE``,
    ``RATE_LIMITER_CHECK_EVERY_N_SECONDS``.
    """
    return PostgresRateLimiter(
        bucket_key=bucket_key,
        requests_per_second=env_config.RATE_LIMITER_REQUESTS_PER_SECOND,
        check_every_n_seconds=env_config.RATE_LIMITER_CHECK_EVERY_N_SECONDS,
        max_bucket_size=env_config.RATE_LIMITER_MAX_BUCKET_SIZE,
    )
