import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import NamedTuple

import aiofiles
import httpx
from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from xxhash import xxh128

from lib.config.env import config
from lib.models.file import FileRole
from lib.services.files import create_file_record
from lib.services.postgres_rate_limiter import PostgresRateLimiter
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# Jina Reader rate limits (requests per minute): 20 anonymously, per source IP;
# 500 with an API key, per key. https://jina.ai/api-dashboard/rate-limit
JINA_ANONYMOUS_RPM = 20
JINA_AUTHENTICATED_RPM = 500


def _jina_headers() -> dict[str, str]:
    """Bearer auth when a key is configured; anonymous otherwise."""
    if config.JINA_API_KEY:
        return {"Authorization": f"Bearer {config.JINA_API_KEY}"}
    return {}


def _jina_rpm() -> int:
    return JINA_AUTHENTICATED_RPM if config.JINA_API_KEY else JINA_ANONYMOUS_RPM


# Backed by Postgres so the cap is enforced across all workers/pods, not per-worker.
jina_rate_limiter = PostgresRateLimiter(
    bucket_key="jina-api",
    requests_per_second=_jina_rpm() / 60,
    check_every_n_seconds=1.0,
    max_bucket_size=_jina_rpm(),
)


class DownloadFileFromUrlResponse(BaseModel):
    file_id: str | None = Field(description="The ID of the downloaded file")
    message: str = Field(
        description="A message with the outcome details of the download operation"
    )
    success: bool = Field(description="Whether the download operation was successful")


@tool()
async def download_file_from_url(
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

    response = await _download_file_from_url_async(url, reference, runtime.context)
    return response.model_dump_json()


async def _download_file_from_url_async(
    url: str, reference: str, context: ContextSchema
) -> DownloadFileFromUrlResponse:
    try:
        saved_file = await _download_direct_url(url)
    except httpx.HTTPError as exc:
        # Includes connect errors and timeouts, so a blocked egress path shows up here.
        logger.warning("Download failed for %s: %s: %s", url, type(exc).__name__, exc)
        return DownloadFileFromUrlResponse(
            file_id=None,
            message=f"Failed to download content from {url}. Error: {exc}",
            success=False,
        )
    except Exception as exc:
        logger.error(
            "Unexpected error downloading %s: %s: %s",
            url,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise

    if saved_file is None:
        logger.warning("Download of %s produced no file", url)
        return DownloadFileFromUrlResponse(
            file_id=None,
            message=f"Failed to download content from {url}: no file produced",
            success=False,
        )

    file_id = await _persist_file_record(
        saved_file=saved_file,
        reference_details=reference,
        project_id=context.project_id,
        user_id=uuid.UUID(context.user_id) if context.user_id else None,
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
    """Download content from URL. Returns SavedFile if successful, None otherwise.

    Any failure of the direct fetch falls back to Jina, which fetches from its own
    network. A blocked egress path usually drops the connection (connect error or
    timeout) instead of answering with an HTTP status, so the fallback cannot be
    limited to status errors.
    """
    try:
        response = await _fetch_pdf_directly(url)
    except Exception as exc:
        logger.warning(
            "Direct fetch of %s failed (%s); falling back to Jina",
            url,
            _describe_error(exc),
        )
        return await _download_with_jina_api(url)

    if response is None:
        return await _download_with_jina_api(url)

    filename = await _save_content(response.content, "pdf")
    logger.info(
        "Saved PDF from %s (%d bytes, final URL %s) as %s",
        url,
        len(response.content),
        response.url,
        filename,
    )
    return SavedFile(filename=filename, content_type="application/pdf")


async def _fetch_pdf_directly(url: str) -> httpx.Response | None:
    """GET the URL; return the response if it is a non-empty PDF, None if it is not a PDF.

    Raises on any fetch failure, including an empty PDF body.
    """
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        logger.info("Downloading %s", url)
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if not content_type.startswith("application/pdf"):
        logger.info(
            "Non-PDF content from %s (Content-Type %r, HTTP %d); converting via Jina",
            url,
            content_type or "missing",
            response.status_code,
        )
        return None

    if not response.content:
        raise ValueError(f"Downloaded PDF from {url} is empty")
    return response


def _describe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return _describe_http_error(exc)
    # Timeouts often stringify to '', so name the exception class explicitly.
    return f"{type(exc).__name__}: {exc}"


def _describe_http_error(exc: httpx.HTTPStatusError) -> str:
    """Status plus who answered and what they said.

    A 403 from a corporate egress proxy, from a publisher's bot protection and from
    r.jina.ai itself all reach the tool as the same exception; the `server` header
    and the first line of the body are what tell them apart in the log.
    """
    response = exc.response
    server = response.headers.get("server", "-")
    via = response.headers.get("via", "-")
    body = response.text[:200].replace("\n", " ") if response.text else ""
    return (
        f"HTTP {response.status_code} final_url={response.url} server={server!r} "
        f"via={via!r} body={body!r}"
    )


def is_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


@retry(
    retry=retry_if_exception(is_rate_limited),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=30, min=30, max=360),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _download_with_jina_api(url: str) -> SavedFile | None:
    """Download content using Jina API and save as markdown. Returns SavedFile if successful, None otherwise."""

    await jina_rate_limiter.aacquire()
    jina_url = f"https://r.jina.ai/{url}"
    headers = _jina_headers()
    logger.info(
        "Fetching %s via Jina reader (%s)",
        url,
        "authenticated" if headers else "anonymous",
    )
    try:
        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            response = await client.get(jina_url, follow_redirects=True)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Logged here, before the caller collapses it into a generic failure, so the
        # log says which hop failed: the publisher or r.jina.ai itself.
        logger.warning("Jina reader failed for %s (%s)", url, _describe_http_error(exc))
        raise
    except httpx.HTTPError as exc:
        # Timeouts often stringify to '', so name the exception class explicitly.
        logger.warning(
            "Jina reader failed for %s: %s: %s", url, type(exc).__name__, exc
        )
        raise

    markdown_content = response.text
    if not markdown_content:
        raise ValueError(f"Jina API returned empty content for {url}")

    filename = await _save_content(markdown_content, "md")
    logger.info(
        "Saved markdown from %s via Jina (%d chars) as %s",
        url,
        len(markdown_content),
        filename,
    )
    return SavedFile(filename=filename, content_type="text/markdown")


async def _persist_file_record(
    saved_file: SavedFile,
    reference_details: str,
    project_id: str,
    user_id: uuid.UUID | None,
) -> str | None:
    """Create a File record for a downloaded file and return its UUID."""
    if not user_id:
        raise ValueError(
            f"Cannot create file record because user_id is missing: user_id={user_id}"
        )

    file_path = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, saved_file.filename)

    if not os.path.exists(file_path):
        raise ValueError(f"Downloaded file not found on disk: {file_path}")

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
            role=FileRole.SUPPORTING_CANDIDATE,
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
            "Content with hash %s already exists at %s; reusing it", xxhash, file_path
        )
        return f"{xxhash}.{extension}"

    # Ensure upload directory exists
    Path(upload_dir).mkdir(parents=True, exist_ok=True)

    # Save the file
    logger.debug(f"Saving downloaded file with hash {xxhash} to {file_path}")
    if isinstance(content, bytes):
        async with aiofiles.open(file_path, "wb") as buffer:
            await buffer.write(content)
    else:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as buffer:
            await buffer.write(content)

    if not os.path.exists(file_path):
        raise Exception(f"File was not created at {file_path}")

    return f"{xxhash}.{extension}"
