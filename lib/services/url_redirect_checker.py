"""URL redirect checker service for validating reference URLs."""

import logging
import re
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s<>\"'\]\)]+", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReferenceValidator/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def extract_url_from_text(text: str) -> Optional[str]:
    """Extract the first URL from reference text."""
    match = URL_PATTERN.search(text)
    if match:
        url = match.group(0)
        return url.rstrip(".,;:!?")
    return None


async def get_final_url(
    reference_text: str,
    timeout: float = 10.0,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the final URL after following redirects.

    Args:
        reference_text: The full reference text that may contain a URL
        timeout: HTTP request timeout in seconds

    Returns:
        Tuple of (original_url, final_url). Both None if no URL found or error.
    """
    original_url = extract_url_from_text(reference_text)

    if not original_url:
        return None, None

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers=HEADERS,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.head(original_url)
            except httpx.HTTPStatusError:
                response = await client.get(original_url)

            final_url = str(response.url)
            return original_url, final_url

    except Exception as e:
        logger.warning(f"Error checking URL redirect for {original_url}: {e}")
        return original_url, None
