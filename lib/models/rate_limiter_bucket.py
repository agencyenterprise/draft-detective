"""Shared token bucket state for the distributed rate limiter."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String
from sqlmodel import Field, SQLModel


class RateLimiterBucket(SQLModel, table=True):
    """A single token bucket, shared across all worker processes.

    The row stores only the state needed to run the token bucket algorithm
    (available tokens + last refill timestamp). The bucket's configuration
    (requests_per_second, max_bucket_size) lives in Python and is supplied
    at acquire time, so tuning limits does not require DB writes.
    """

    __tablename__ = "rate_limiter_buckets"

    bucket_key: str = Field(
        sa_column=Column(String, primary_key=True),
        description="Opaque identifier for the bucket (e.g. a hashed API key).",
    )
    available_tokens: float = Field(
        sa_column=Column(Float, nullable=False),
        description="Number of tokens currently available in the bucket.",
    )
    last_refill_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Last time the bucket was refilled; used to compute elapsed refill.",
    )
