"""
Text matching utilities for mapping chunks to document elements.

Uses rapidfuzz for fuzzy matching which handles:
- Unicode variations (curly quotes, dashes, etc.)
- Substring matching (chunk contained in paragraph)
- Whitespace differences
- Minor character variations
"""

from rapidfuzz import fuzz

# Minimum similarity score (0-100) for a match
MATCH_THRESHOLD = 85.0


def _normalize_minimal(text: str) -> str:
    """Minimal normalization - just whitespace and case."""
    return " ".join(text.lower().split())


def text_matches(text1: str, text2: str, threshold: float = MATCH_THRESHOLD) -> bool:
    """
    Check if two texts match using fuzzy similarity.

    Uses rapidfuzz partial_ratio which naturally handles:
    - Unicode quote/dash variants (high similarity to ASCII equivalents)
    - Substring matching (chunk contained in paragraph)
    - Whitespace differences
    - Minor character variations

    Args:
        text1: First text to compare
        text2: Second text to compare
        threshold: Minimum similarity score (0-100)

    Returns:
        True if texts are sufficiently similar
    """
    t1 = _normalize_minimal(text1)
    t2 = _normalize_minimal(text2)

    if not t1 or not t2:
        return False

    return fuzz.partial_ratio(t1, t2) >= threshold
