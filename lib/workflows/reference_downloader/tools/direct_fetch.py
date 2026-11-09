"""Fetch a reference straight from the server the document names.

The server is whoever the document's author chose, so the fetch is held to public
addresses (``url_guard``) and to a size and a time it may take.
"""

import asyncio
import logging
from typing import NamedTuple

import httpx

from lib.workflows.reference_downloader.tools.url_guard import direct_client

logger = logging.getLogger(__name__)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# A direct fetch reads the body into memory, and the server is whoever the
# document names. Past this size the fetch fails and Jina is asked instead.
MAX_DIRECT_DOWNLOAD_BYTES = 100 * 1024 * 1024
# httpx's timeout is per read, so a server sending a byte at a time would never
# trip it; this bounds the whole fetch.
DIRECT_DOWNLOAD_DEADLINE_SECONDS = 180.0
# How much of an error answer is kept for the log.
_ERROR_BODY_HEAD_BYTES = 4096


class DirectPdf(NamedTuple):
    content: bytes
    final_url: httpx.URL


class ResponseTooLargeError(ValueError):
    """The answer is larger than a direct fetch may read."""


async def fetch_pdf_directly(url: str) -> DirectPdf | None:
    """GET the URL; return its body if it is a non-empty PDF, None if it is not a PDF.

    The body is streamed: a non-PDF answer is never read, and a PDF one is read only
    up to ``MAX_DIRECT_DOWNLOAD_BYTES`` and ``DIRECT_DOWNLOAD_DEADLINE_SECONDS``.

    Raises on any fetch failure, including an empty, oversized or too slow PDF body,
    and with ``BlockedUrlError`` when the URL or a redirect hop is not a public
    address.
    """
    logger.info("Downloading %s", url)
    async with (
        asyncio.timeout(DIRECT_DOWNLOAD_DEADLINE_SECONDS),
        direct_client(timeout=30.0, headers=headers) as client,
        client.stream("GET", url, follow_redirects=True) as response,
    ):
        if response.is_error:
            await _raise_for_status(response)

        content_type = response.headers.get("Content-Type", "").lower()
        if not content_type.startswith("application/pdf"):
            logger.info(
                "Non-PDF content from %s (Content-Type %r, HTTP %d); converting via Jina",
                url,
                content_type or "missing",
                response.status_code,
            )
            return None

        content = await _read_capped(response, MAX_DIRECT_DOWNLOAD_BYTES)

    if not content:
        raise ValueError(f"Downloaded PDF from {url} is empty")
    return DirectPdf(content=content, final_url=response.url)


async def _read_capped(response: httpx.Response, limit: int) -> bytes:
    """The streamed body, decoded, or ``ResponseTooLargeError`` once it passes ``limit``."""

    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > limit:
            raise ResponseTooLargeError(
                f"{response.url} answered with more than {limit} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _raise_for_status(response: httpx.Response) -> None:
    """Raise ``HTTPStatusError`` for a streamed error answer, keeping the start of its
    body for the log without reading the rest."""

    head = b""
    async for chunk in response.aiter_bytes():
        head += chunk
        if len(head) >= _ERROR_BODY_HEAD_BYTES:
            break
    # The head is already decoded, so the encoding headers no longer describe it.
    kept = [
        (name, value)
        for name, value in response.headers.multi_items()
        if name.lower() not in ("content-encoding", "content-length")
    ]
    httpx.Response(
        response.status_code,
        headers=kept,
        content=head[:_ERROR_BODY_HEAD_BYTES],
        request=response.request,
    ).raise_for_status()
