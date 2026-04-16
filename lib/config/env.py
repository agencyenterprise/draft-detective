import json
import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Config(BaseModel):
    OPENAI_API_KEY: Optional[str]

    # Logging Configuration
    LOG_RICH_HANDLER: bool = Field(
        default=False,
        description="Whether to use the rich handler for logging (recommended for development only)",
    )

    # Langfuse Configuration
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = None
    LANGFUSE_PROJECT_ID: Optional[str] = None

    # Langgraph Configuration
    LANGGRAPH_MAX_CONCURRENCY: int = Field(
        default=30,
        description="The maximum number of concurrent langgraph nodes to execute in parallel",
    )

    # Database Configuration
    DATABASE_URL: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # Authentication
    AUTH_SECRET: str = Field(
        description="The secret key for the authentication. This is used to sign and verify JWT tokens. Shared by the frontend and backend.",
    )

    # MCP / OAuth Authentication
    AUTH_GOOGLE_ID: Optional[str] = None
    AUTH_GOOGLE_SECRET: Optional[str] = None
    AUTH_MICROSOFT_ENTRA_ID_ID: Optional[str] = None
    AUTH_MICROSOFT_ENTRA_ID_SECRET: Optional[str] = None
    AUTH_MICROSOFT_ENTRA_ID_ISSUER: Optional[str] = None
    MCP_BASE_URL: str = Field(
        default="http://localhost:8000/mcp",
        description="Public URL of the MCP server (must include /mcp path)",
    )
    MCP_CIMD_ENABLED: bool = Field(
        default=False,
        description="Whether to enable CIMD for MCP OAuth providers. Disable if clients are behind VPNs that cannot reach the CIMD endpoint.",
    )

    # File uploads
    FILE_UPLOADS_MOUNT_PATH: str

    # Resumable upload configuration
    UPLOAD_CHUNK_SIZE: int = Field(
        default=5 * 1024 * 1024,
        description="Chunk size for resumable uploads in bytes (default: 5MB)",
    )
    UPLOAD_SESSION_TTL_HOURS: int = Field(
        default=24,
        description="Upload session time-to-live in hours (default: 24)",
    )

    # Frontend URL for share links
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Base URL for the frontend application (used for share links)",
    )

    # Per-model API key overrides (JSON dict mapping model name → API key)
    # Example: {"gpt-5-mini-2025-08-07": "sk-xxx", "gpt-4.1-2025-04-14": "sk-yyy"}
    MODEL_API_KEYS: dict[str, str] = Field(
        default_factory=dict,
        description="Per-model API key overrides. Keys are model names (e.g. Azure deployment IDs).",
    )

    # Rate limiter configuration (shared across workers via Postgres)
    RATE_LIMITER_REQUESTS_PER_SECOND: float = Field(
        default=2,
        description="Average LLM requests-per-second cap enforced globally across workers",
    )
    RATE_LIMITER_MAX_BUCKET_SIZE: float = Field(
        default=1,
        description="Maximum burst size (token bucket ceiling); must be >= 1",
    )
    RATE_LIMITER_CHECK_EVERY_N_SECONDS: float = Field(
        default=0.2,
        description="Polling interval when the bucket is empty and the caller is blocking",
    )


config = Config(
    OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
    LOG_RICH_HANDLER=os.getenv("LOG_RICH_HANDLER", "false").lower() == "true",
    LANGFUSE_HOST=os.getenv("LANGFUSE_HOST"),
    LANGFUSE_SECRET_KEY=os.getenv("LANGFUSE_SECRET_KEY"),
    LANGFUSE_PUBLIC_KEY=os.getenv("LANGFUSE_PUBLIC_KEY"),
    LANGFUSE_PROJECT_ID=os.getenv("LANGFUSE_PROJECT_ID"),
    LANGGRAPH_MAX_CONCURRENCY=os.getenv("LANGGRAPH_MAX_CONCURRENCY") or 30,
    FILE_UPLOADS_MOUNT_PATH=os.getenv("FILE_UPLOADS_MOUNT_PATH", "uploads"),
    UPLOAD_CHUNK_SIZE=int(os.getenv("UPLOAD_CHUNK_SIZE", str(5 * 1024 * 1024))),
    UPLOAD_SESSION_TTL_HOURS=int(os.getenv("UPLOAD_SESSION_TTL_HOURS", "24")),
    FRONTEND_URL=os.getenv("FRONTEND_URL", "http://localhost:3000"),
    DATABASE_URL=os.getenv("DATABASE_URL"),
    POSTGRES_HOST=os.getenv("POSTGRES_HOST"),
    POSTGRES_PORT=os.getenv("POSTGRES_PORT"),
    POSTGRES_DB=os.getenv("POSTGRES_DB"),
    POSTGRES_USER=os.getenv("POSTGRES_USER"),
    POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD"),
    AUTH_SECRET=os.getenv("AUTH_SECRET"),
    AUTH_GOOGLE_ID=os.getenv("AUTH_GOOGLE_ID"),
    AUTH_GOOGLE_SECRET=os.getenv("AUTH_GOOGLE_SECRET"),
    AUTH_MICROSOFT_ENTRA_ID_ID=os.getenv("AUTH_MICROSOFT_ENTRA_ID_ID"),
    AUTH_MICROSOFT_ENTRA_ID_SECRET=os.getenv("AUTH_MICROSOFT_ENTRA_ID_SECRET"),
    AUTH_MICROSOFT_ENTRA_ID_ISSUER=os.getenv("AUTH_MICROSOFT_ENTRA_ID_ISSUER"),
    MCP_BASE_URL=os.getenv("MCP_BASE_URL", "http://localhost:8000/mcp"),
    MCP_CIMD_ENABLED=os.getenv("MCP_CIMD_ENABLED", "false").lower() == "true",
    RATE_LIMITER_REQUESTS_PER_SECOND=float(
        os.getenv("RATE_LIMITER_REQUESTS_PER_SECOND", "2")
    ),
    RATE_LIMITER_MAX_BUCKET_SIZE=float(os.getenv("RATE_LIMITER_MAX_BUCKET_SIZE", "1")),
    RATE_LIMITER_CHECK_EVERY_N_SECONDS=float(
        os.getenv("RATE_LIMITER_CHECK_EVERY_N_SECONDS", "0.2")
    ),
    MODEL_API_KEYS=json.loads(os.getenv("MODEL_API_KEYS", "{}")),
)


def get_model_api_key(model_name: str) -> str | None:
    """Return the API key configured for a specific model name, or None."""
    return config.MODEL_API_KEYS.get(model_name)
