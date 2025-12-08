import logging
import os
from pathlib import Path

import httpx
from langgraph.runtime import Runtime
from xxhash import xxh128

from lib.config.env import config
from lib.run_utils import run_tasks
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchConclusion,
    ReferenceFetchItem,
)
from lib.workflows.reference_downloader.state import ReferenceDownloaderState

logger = logging.getLogger(__name__)


@register_node(
    "Download references",
    "Download references from the internet",
)
async def download_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
) -> ReferenceDownloaderState:
    references = state.fetched_references or []

    tasks = [_download_reference(reference) for reference in references]
    results: tuple[list[str | None], list[Exception]] = await run_tasks(
        tasks, desc="Downloading references", max_concurrent=10
    )
    downloaded_references, errors = results

    return {"downloaded_references": downloaded_references}


async def _download_reference(
    reference: ReferenceFetchItem,
) -> str | None:
    """Download content from the reference URL and save it to the uploads directory.

    Downloads PDFs directly, or uses Jina API to convert non-PDF content to markdown.
    Returns the filename if successful, None otherwise.
    """

    # Only download if source was found
    if reference.final_conclusion != ReferenceFetchConclusion.SOURCE_FOUND:
        logger.info(
            f"Skipping download for reference with conclusion: {reference.final_conclusion}"
        )
        return None

    url = reference.download_url or reference.source_url

    if not url:
        logger.warning(f"No URL available for reference: {reference.reference_details}")
        return None

    return await _download_direct_url(url)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


async def _download_direct_url(url: str) -> str | None:
    """Download content from URL. Returns filename if successful, None otherwise."""
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
                return filename
            else:
                # Not a PDF, use Jina to convert to markdown
                logger.info(
                    f"Content is not PDF (Content-Type: {content_type}), using Jina to convert to markdown"
                )
                return await _download_with_jina_api(url)

    except Exception:
        logger.warning(
            f"Error downloading content from {url}, falling back to Jina", exc_info=True
        )
        return await _download_with_jina_api(url)


async def _download_with_jina_api(url: str) -> str | None:
    """Download content using Jina API and save as markdown. Returns filename if successful, None otherwise."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            logger.info(f"Downloading content with Jina API from {url}")
            response = await client.get(
                f"https://r.jina.ai/{url}", follow_redirects=True
            )
            response.raise_for_status()

            markdown_content = response.text
            if not markdown_content:
                logger.warning(f"Jina API returned empty content for {url}")
                return None

            filename = await _save_content(markdown_content, "md")
            logger.info(f"Successfully downloaded and saved markdown to {filename}")
            return filename
    except Exception:
        logger.error(
            f"Error downloading content with Jina API from {url}", exc_info=True
        )
        return None


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


if __name__ == "__main__":
    import asyncio
    from lib.config.logger import setup_logger

    setup_logger()

    asyncio.run(
        _download_direct_url(
            "https://www.rand.org/content/dam/rand/pubs/research_reports/RR1700/RR1751/RAND_RR1751.pdf"
        )
    )
