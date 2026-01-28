"""
Procedural detection for advocacy and tone issues.

Fast regex + TextBlob checks that run before LLM verification.
"""

import re
from typing import List

from textblob import TextBlob  # type: ignore[import-untyped]

from lib.workflows.advocacy_tone.constants import (
    ADVOCACY_PATTERNS,
    IGNORED_SECTION_KEYWORDS,
    SUBJECTIVITY_THRESHOLD,
    TRIGGER_WORDS,
)
from lib.workflows.advocacy_tone.state import ProceduralFlags
from lib.workflows.chunk_utils import AnalyzedChunk

# Pre-compiled patterns for efficiency
_trigger_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in TRIGGER_WORDS) + r")\b",
    re.IGNORECASE,
)
_advocacy_patterns = [re.compile(p, re.IGNORECASE) for p in ADVOCACY_PATTERNS]


def should_skip_chunk(chunk: AnalyzedChunk) -> bool:
    """Check if chunk should be skipped based on section headings."""
    if not chunk.headings:
        return False
    combined = " ".join(chunk.headings).lower()
    return any(kw in combined for kw in IGNORED_SECTION_KEYWORDS)


def detect_flags(text: str) -> ProceduralFlags:
    """Run all procedural checks on text.
    
    Returns flags indicating which checks failed (need LLM verification).
    """
    return ProceduralFlags(
        trigger_words=bool(_trigger_pattern.search(text)),
        advocacy_language=any(p.search(text) for p in _advocacy_patterns),
        subjective_tone=TextBlob(text).sentiment.subjectivity > SUBJECTIVITY_THRESHOLD,
    )


def has_any_flag(flags: ProceduralFlags) -> bool:
    """Check if any procedural flag is set."""
    return flags.trigger_words or flags.advocacy_language or flags.subjective_tone


def build_context(chunks: List[AnalyzedChunk], target: AnalyzedChunk, k: int) -> str:
    """Build context string with k chunks before/after target."""
    idx = next((i for i, c in enumerate(chunks) if c.chunk_index == target.chunk_index), 0)
    start, end = max(0, idx - k), min(len(chunks), idx + k + 1)
    
    parts = []
    for i in range(start, end):
        prefix = "[Target]" if i == idx else "[Before]" if i < idx else "[After]"
        parts.append(f"{prefix} {chunks[i].content}")
    
    return "\n".join(parts)

