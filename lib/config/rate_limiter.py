import hashlib
from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter


def hash_api_key(api_key: str) -> str:
    """Return a short hash of an API key suitable for use as a rate-limiter key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


@lru_cache(maxsize=256)
def get_rate_limiter(api_key_hash: str) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(
        requests_per_second=64,
        check_every_n_seconds=0.2,
        max_bucket_size=200,
    )
