"""Shared key-value state for FastMCP OAuth providers.

FastMCP's OAuth providers keep client registrations, authorization codes, and
PKCE state in a pluggable ``AsyncKeyValue`` store. The default is in-memory,
which breaks in multi-pod deployments: pod A stores the registration, pod B
gets the browser callback, and the handoff hangs. Persisting the state here
lets any pod resume any flow.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class MCPOAuthKV(SQLModel, table=True):
    __tablename__ = "mcp_oauth_kv"

    collection: str = Field(
        sa_column=Column(String, primary_key=True),
        description="Logical namespace for the key (FastMCP uses this to separate client registrations, tokens, etc.).",
    )
    key: str = Field(
        sa_column=Column(String, primary_key=True),
        description="Entry key within the collection.",
    )
    value: dict = Field(
        sa_column=Column(JSONB, nullable=False),
        description="Opaque payload. Already encrypted by FernetEncryptionWrapper before reaching this row.",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When this entry was written.",
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
        description="Optional absolute expiry. Rows past this are treated as missing and cleaned up lazily on read.",
    )
