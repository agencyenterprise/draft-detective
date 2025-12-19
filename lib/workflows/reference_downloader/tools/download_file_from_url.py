import asyncio
import logging
import mimetypes
import os
from pathlib import Path
import re
from typing import NamedTuple
import uuid

import httpx
from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field
from xxhash import xxh128

from lib.config.env import config
from lib.models.file import FileRole
from lib.services.files import create_file_record
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


class DownloadFileFromUrlResponse(BaseModel):
    file_id: str | None = Field(description="The ID of the downloaded file")
    message: str = Field(
        description="A message with the outcome details of the download operation"
    )
    success: bool = Field(description="Whether the download operation was successful")


@tool()
def download_file_from_url(
    url: str, reference: str, runtime: ToolRuntime[ContextSchema]
) -> str:
    """
    Download a file from a URL.

    Args:
        url: The URL of the file to download.
        reference: The original reference text of the file being downloaded.

    Returns:
        A JSON string with the response from the download operation, containing the fields:
        - file_id: The ID of the downloaded file or null if the download operation failed
        - message: A message with the outcome details of the download operation or the error message if the download operation failed
        - success: Whether the download operation was successful or false if it failed
    """

    response = asyncio.run(
        _download_file_from_url_async(url, reference, runtime.context)
    )
    return response.model_dump_json()


async def _download_file_from_url_async(
    url: str, reference: str, context: ContextSchema
) -> DownloadFileFromUrlResponse:
    try:
        saved_file = await _download_direct_url(url)
    except httpx.HTTPError as exc:
        logger.warning(
            f"Warning: Failed to download content from {url} (HTTP Error: {exc})"
        )
        return DownloadFileFromUrlResponse(
            file_id=None,
            message=f"Failed to download content from {url}. Error: {exc}",
            success=False,
        )
    except Exception as exc:
        logger.error(f"Error downloading content from {url} (error: {exc})")
        raise

    file_id = await _persist_file_record(
        saved_file=saved_file,
        reference_details=reference,
        project_id=context.project_id,
        user_id=context.user_id,
    )

    return DownloadFileFromUrlResponse(
        file_id=file_id,
        message=f"Successfully downloaded content from {url} and saved to file with ID {file_id}",
        success=True,
    )


class SavedFile(NamedTuple):
    filename: str
    content_type: str


async def _download_direct_url(url: str) -> SavedFile | None:
    """Download content from URL. Returns SavedFile if successful, None otherwise."""
    try:

        # Download the file and check content type
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            logger.info(f"Downloading file from {url}")
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Check if the response is a PDF based on Content-Type header
            content_type = response.headers.get("Content-Type", "").lower()

            if content_type.startswith("application/pdf"):
                # Save as PDF
                content = response.content

                if len(content) == 0:
                    logger.warning(f"Downloaded file from {url} is empty")
                    return None

                filename = await _save_content(content, "pdf")
                logger.info(f"Successfully downloaded and saved PDF to {filename}")
                return SavedFile(filename=filename, content_type="application/pdf")
            else:
                # Not a PDF, use Jina to convert to markdown
                logger.info(
                    f"Content is not PDF (Content-Type: {content_type}), using Jina to convert to markdown"
                )
                return await _download_with_jina_api(url)

    except httpx.HTTPStatusError as exc:
        logger.warning(
            f"Error downloading content from {url}, falling back to Jina (HTTP status error: {exc})"
        )
        return await _download_with_jina_api(url)


async def _download_with_jina_api(url: str) -> SavedFile | None:
    """Download content using Jina API and save as markdown. Returns SavedFile if successful, None otherwise."""

    async with httpx.AsyncClient(timeout=120.0) as client:
        logger.info(f"Downloading content with Jina API from {url}")
        response = await client.get(f"https://r.jina.ai/{url}", follow_redirects=True)
        response.raise_for_status()

        markdown_content = response.text
        if not markdown_content:
            logger.warning(f"Jina API returned empty content for {url}")
            return None

        filename = await _save_content(markdown_content, "md")
        logger.info(f"Successfully downloaded and saved markdown to {filename}")
        return SavedFile(filename=filename, content_type="text/markdown")


async def _persist_file_record(
    saved_file: SavedFile,
    reference_details: str,
    project_id: str | None,
    user_id: uuid.UUID | None,
) -> str | None:
    """Create a File record for a downloaded file and return its UUID."""
    if not project_id or not user_id:
        logger.warning(
            "Cannot create file record because project_id or user_id is missing"
        )
        return None

    file_path = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, saved_file.filename)

    if not os.path.exists(file_path):
        logger.warning(f"Downloaded file not found on disk: {file_path}")
        return None

    content_hash, extension = _split_filename(saved_file.filename)
    file_size = os.path.getsize(file_path)
    file_name = _build_file_name(reference_details, extension)
    file_type = (
        saved_file.content_type
        or mimetypes.guess_type(file_name)[0]
        or "application/octet-stream"
    )

    try:
        project_uuid = uuid.UUID(str(project_id))
        user_id_uuid = uuid.UUID(str(user_id))

        description = f"[This file was automatically downloaded for the reference: {reference_details}]"

        file = await create_file_record(
            project_id=project_uuid,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            content_hash=content_hash,
            role=FileRole.SUPPORT,
            uploaded_by=user_id_uuid,
            original_file_path=None,
            description=description,
        )

        return str(file.id)
    except Exception as exc:
        logger.error(
            f"Failed to create file record for {file_path}: {exc}", exc_info=True
        )
        return None


def _split_filename(filename: str) -> tuple[str, str]:
    """Split hashed filename into (hash, extension)."""
    base, ext = os.path.splitext(filename)
    extension = ext.lstrip(".") or "bin"
    return base, extension


def _build_file_name(reference_details: str, extension: str) -> str:
    """Generate a user-friendly file name based on the reference details."""
    sanitized = re.sub(r"[^a-z0-9]+", "_", reference_details.lower()).strip("_")
    trimmed = sanitized[:80] if sanitized else "reference"
    return f"{trimmed}.{extension}"


async def _save_content(content: bytes | str, extension: str) -> str:
    """Save content to file. Returns the filename.

    Args:
        content: The content to save (bytes for binary files, str for text files)
        extension: File extension (e.g., 'pdf', 'md')
    """

    # Calculate hash from bytes
    content_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
    xxhash = xxh128(content_bytes).hexdigest()
    upload_dir = config.FILE_UPLOADS_MOUNT_PATH
    file_path = os.path.join(upload_dir, f"{xxhash}.{extension}")

    # Skip if file already exists
    if os.path.exists(file_path):
        logger.info(
            f"File with hash {xxhash} already exists at {file_path}, skipping download"
        )
        return f"{xxhash}.{extension}"

    # Ensure upload directory exists
    Path(upload_dir).mkdir(parents=True, exist_ok=True)

    # Save the file
    logger.info(f"Saving downloaded file with hash {xxhash} to {file_path}")
    if isinstance(content, bytes):
        with open(file_path, "wb") as buffer:
            buffer.write(content)
    else:
        with open(file_path, "w", encoding="utf-8") as buffer:
            buffer.write(content)

    if not os.path.exists(file_path):
        raise Exception(f"File was not created at {file_path}")

    return f"{xxhash}.{extension}"
