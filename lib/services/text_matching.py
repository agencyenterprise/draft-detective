"""
Text matching utilities for mapping chunks to document elements.
"""

import re


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent matching.

    Returns:
        Normalized text (lowercase, whitespace collapsed, stripped)
    """
    return re.sub(r"\s+", " ", text.lower().strip())


def text_matches(text1: str, text2: str) -> bool:
    """
    Check if two texts match via exact or substring matching.

    Returns:
        True if texts match (exact or substring), False otherwise
    """
    normalized1 = normalize_text(text1)
    normalized2 = normalize_text(text2)

    if not normalized1 or not normalized2:
        return False

    return (
        normalized1 == normalized2
        or normalized1 in normalized2
        or normalized2 in normalized1
    )
