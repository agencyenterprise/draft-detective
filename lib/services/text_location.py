"""Finding a span of text in a longer one, ignoring how the whitespace fell.

A quote and the passage it was taken from drift at the character level: about
half of the converted DOCX documents carry non-breaking spaces inside prose,
double spaces appear before footnote markers, and a Word paragraph wraps its
own way. So matching is done on a whitespace-normalized basis, but every span
handed back indexes the *raw* text, which is what a caller has to search the
document for or build a Range over.

Pure functions only, and nothing here knows about markdown.
"""

import re
from typing import List, Tuple

# The same class `normalize_whitespace` collapses, one character at a time.
_WHITESPACE = re.compile(r"\s")


def all_offsets(haystack: str, needle: str) -> List[int]:
    """Start offset of every occurrence of `needle`, overlapping ones included."""
    offsets: List[int] = []
    if not needle:
        return offsets
    position = haystack.find(needle)
    while position != -1:
        offsets.append(position)
        position = haystack.find(needle, position + 1)
    return offsets


def _normalized_index(text: str) -> Tuple[str, List[int]]:
    """Whitespace-normalize `text`, keeping each character's source offset.

    Mirrors the frontend's `buildTextIndex`: a run of whitespace collapses to
    one space, a leading run to nothing, and the space is emitted just before
    the character that ended the run -- so both share that character's offset.
    The mapping is what lets a normalized match be handed back as the exact
    substring of the original, non-breaking spaces and all.
    """
    normalized: List[str] = []
    sources: List[int] = []
    pending_space = False
    for offset, char in enumerate(text):
        if _WHITESPACE.match(char):
            pending_space = bool(normalized)
            continue
        if pending_space:
            normalized.append(" ")
            sources.append(offset)
            pending_space = False
        normalized.append(char)
        sources.append(offset)
    return "".join(normalized), sources


def locate_in_paragraph(paragraph_text: str, needle: str) -> List[Tuple[int, int]]:
    """Every occurrence of `needle` in `paragraph_text`, as original-text spans.

    `needle` is matched on a whitespace-normalized basis (the paragraph and the
    quote drift at the character level: non-breaking spaces inside prose,
    double spaces before footnote markers), but each returned ``[start, end)``
    indexes `paragraph_text` itself, so ``paragraph_text[start:end]`` is the
    exact substring to search the document for.

    Matching is case-sensitive: the export writes a redline, so a span that
    only matches once the case is ignored is left for a human to place.
    """
    if not needle:
        return []
    normalized, sources = _normalized_index(paragraph_text)
    spans: List[Tuple[int, int]] = []
    for offset in all_offsets(normalized, needle):
        spans.append((sources[offset], sources[offset + len(needle) - 1] + 1))
    return spans
