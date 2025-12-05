"""Text matching using rapidfuzz fuzzy similarity."""

from rapidfuzz import fuzz, utils

MATCH_THRESHOLD = 85.0


def text_matches(text1: str, text2: str, threshold: float = MATCH_THRESHOLD) -> bool:
    """
    Check if two texts match using fuzzy similarity.

    Uses rapidfuzz partial_ratio with default_process which handles:
    - Lowercasing
    - Whitespace normalization
    - Non-alphanumeric removal (handles quotes, dashes, unicode variants)

    Args:
        text1: First text to compare
        text2: Second text to compare
        threshold: Minimum similarity score (0-100)

    Returns:
        True if texts are sufficiently similar
    """
    if not text1 or not text2:
        return False

    return (
        fuzz.partial_ratio(text1, text2, processor=utils.default_process) >= threshold
    )
