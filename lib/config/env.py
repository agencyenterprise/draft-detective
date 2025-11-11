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

    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_HOST: str
    LANGFUSE_PROJECT_ID: str

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

    # File conversion
    FILE_CONVERTER: str = Field(
        default="markitdown",
        description="The converter to use for file to markdown conversion ('markitdown' or 'docling')",
    )
    DOCLING_SERVE_API_URL: Optional[str] = Field(
        default=None,
        description="Base URL for the docling-serve API (required when FILE_CONVERTER=docling)",
    )
    DOCLING_SERVE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for the docling-serve API (required when FILE_CONVERTER=docling)",
    )

    @model_validator(mode="after")
    def validate_openai_config(self):
        """Validate that either OpenAI API key or Azure OpenAI credentials are present."""

        has_openai_key = (
            self.OPENAI_API_KEY is not None and self.OPENAI_API_KEY.strip() != ""
        )
        has_azure_config = all(
            [
                field is not None and field.strip() != ""
                for field in [
                    self.AZURE_OPENAI_API_KEY,
                    self.AZURE_OPENAI_ENDPOINT,
                    self.OPENAI_API_VERSION,
                ]
            ]
        )

        if not has_openai_key and not has_azure_config:
            raise ValueError(
                "Either OPENAI_API_KEY or all of AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and OPENAI_API_VERSION must be provided"
            )

        return self

    @model_validator(mode="after")
    def validate_docling_serve_api(self):
        if self.FILE_CONVERTER == "docling" and not self.DOCLING_SERVE_API_URL:
            raise ValueError(
                "DOCLING_SERVE_API_URL must be provided when FILE_CONVERTER=docling"
            )

        if self.FILE_CONVERTER == "docling" and not self.DOCLING_SERVE_API_KEY:
            raise ValueError(
                "DOCLING_SERVE_API_KEY must be provided when FILE_CONVERTER=docling"
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
    FILE_UPLOADS_MOUNT_PATH=os.getenv("FILE_UPLOADS_MOUNT_PATH", "uploads"),
    FILE_CONVERTER=os.getenv("FILE_CONVERTER", "markitdown"),
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
