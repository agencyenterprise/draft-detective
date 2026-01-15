import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv()


class Config(BaseModel):
    OPENAI_API_KEY: Optional[str]
    OPENAI_API_VERSION: Optional[str]
    AZURE_OPENAI_API_KEY: Optional[str]
    AZURE_OPENAI_ENDPOINT: Optional[str]

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

    # File uploads
    FILE_UPLOADS_MOUNT_PATH: str

    # Frontend URL for share links
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Base URL for the frontend application (used for share links)",
    )

    # File conversion
    MAIN_FILE_CONVERTER: str = Field(
        default="docling",
        description="The converter to use for main document conversion ('markitdown' or 'docling')",
    )
    SUPPORTING_FILE_CONVERTER: str = Field(
        default="markitdown",
        description="The converter to use for supporting documents conversion ('markitdown' or 'docling')",
    )
    DOCLING_SERVE_API_URL: Optional[str] = Field(
        default=None,
        description="Base URL for the docling-serve API (required when using docling converter)",
    )
    DOCLING_SERVE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for the docling-serve API (required when using docling converter)",
    )

    @model_validator(mode="after")
    def validate_docling_serve_api(self):
        # Check if docling is used for either main or supporting files
        uses_docling = (
            self.MAIN_FILE_CONVERTER == "docling"
            or self.SUPPORTING_FILE_CONVERTER == "docling"
        )

        if uses_docling and not self.DOCLING_SERVE_API_URL:
            raise ValueError(
                "DOCLING_SERVE_API_URL must be provided when using docling converter"
            )

        if uses_docling and not self.DOCLING_SERVE_API_KEY:
            raise ValueError(
                "DOCLING_SERVE_API_KEY must be provided when using docling converter"
            )

        return self


config = Config(
    OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
    OPENAI_API_VERSION=os.getenv("OPENAI_API_VERSION"),
    AZURE_OPENAI_API_KEY=os.getenv("AZURE_OPENAI_API_KEY"),
    AZURE_OPENAI_ENDPOINT=os.getenv("AZURE_OPENAI_ENDPOINT"),
    LANGFUSE_HOST=os.getenv("LANGFUSE_HOST"),
    LANGFUSE_SECRET_KEY=os.getenv("LANGFUSE_SECRET_KEY"),
    LANGFUSE_PUBLIC_KEY=os.getenv("LANGFUSE_PUBLIC_KEY"),
    LANGFUSE_PROJECT_ID=os.getenv("LANGFUSE_PROJECT_ID"),
    LANGGRAPH_MAX_CONCURRENCY=os.getenv("LANGGRAPH_MAX_CONCURRENCY") or 30,
    FILE_UPLOADS_MOUNT_PATH=os.getenv("FILE_UPLOADS_MOUNT_PATH", "uploads"),
    FRONTEND_URL=os.getenv("FRONTEND_URL", "http://localhost:3000"),
    MAIN_FILE_CONVERTER=os.getenv("MAIN_FILE_CONVERTER", "docling"),
    SUPPORTING_FILE_CONVERTER=os.getenv("SUPPORTING_FILE_CONVERTER", "markitdown"),
    DOCLING_SERVE_API_URL=os.getenv("DOCLING_SERVE_API_URL"),
    DOCLING_SERVE_API_KEY=os.getenv("DOCLING_SERVE_API_KEY"),
    DATABASE_URL=os.getenv("DATABASE_URL"),
    POSTGRES_HOST=os.getenv("POSTGRES_HOST"),
    POSTGRES_PORT=os.getenv("POSTGRES_PORT"),
    POSTGRES_DB=os.getenv("POSTGRES_DB"),
    POSTGRES_USER=os.getenv("POSTGRES_USER"),
    POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD"),
    AUTH_SECRET=os.getenv("AUTH_SECRET"),
)
