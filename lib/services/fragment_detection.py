"""
Fragment Detection Strategies for Sentence Tokenization.

This module provides multiple strategies for detecting when NLTK's sentence
tokenization has produced suspicious fragments (e.g., incorrectly split citations).
"""

from typing import List, Literal, Optional, Dict
import re
import numpy as np


DetectionMethod = Literal["reconstruction", "semantic", "statistical"]

# Global suspicion threshold used across all detection methods
SUSPICION_THRESHOLD = 5


def _filter_empty_sentences(sentences: List[str]) -> List[str]:
    """Remove empty/whitespace-only sentences."""
    return [s.strip() for s in sentences if s.strip()]


# Fragment statistics constants
MIN_FRAGMENT_LENGTH = 15
EXTREMELY_SHORT_FRAGMENT_LENGTH = 10
SHORT_FRAGMENT_PENALTY = 2


def _calculate_fragment_stats(sentences: List[str]) -> Optional[Dict]:
    """Calculate statistics for fragment analysis."""
    lengths = [len(s.strip()) for s in sentences if s.strip()]

    if not lengths:
        return None

    avg_length = sum(lengths) / len(lengths)

    return {
        "lengths": lengths,
        "avg_length": avg_length,
        "min_length": min(lengths),
        "max_length": max(lengths),
        "very_short_count": sum(1 for l in lengths if l < MIN_FRAGMENT_LENGTH),
        "extremely_short_count": sum(
            1 for l in lengths if l < EXTREMELY_SHORT_FRAGMENT_LENGTH
        ),
    }


# Fragment scoring constants
VERY_SHORT_PENALTY = 3
VERY_SHORT_MULTIPLE_PENALTY = 2
EXTREMELY_SHORT_PENALTY = 2
MIN_FRAGMENTS_FOR_BIMODAL = 2
MIN_BIMODAL_LENGTH = 40
BIMODAL_RATIO_THRESHOLD = 4
BIMODAL_PENALTY = 2


def _score_fragment_lengths(stats: Dict) -> int:
    """Score fragments based on length anomalies."""
    score = 0

    if stats["very_short_count"] >= 1:
        score += VERY_SHORT_PENALTY
    if stats["very_short_count"] >= 2:
        score += VERY_SHORT_MULTIPLE_PENALTY

    if stats["extremely_short_count"] >= 1:
        score += EXTREMELY_SHORT_PENALTY

    # Bimodal distribution
    if len(stats["lengths"]) >= MIN_FRAGMENTS_FOR_BIMODAL:
        if (
            stats["min_length"] < MIN_FRAGMENT_LENGTH
            and stats["max_length"] > MIN_BIMODAL_LENGTH
            and (stats["max_length"] / stats["min_length"]) > BIMODAL_RATIO_THRESHOLD
        ):
            score += BIMODAL_PENALTY

    return score


# Reconstruction quality detection constants
MIN_FRAGMENTS_FOR_CV = 3
COEFFICIENT_OF_VARIATION_THRESHOLD = 0.6
SUSPICIOUS_FRAGMENT_LENGTH = 20
HIGH_CV_PENALTY = 2
VERY_SHORT_FRAGMENT_LENGTH = 10
PARENTHETICAL_FRAGMENT_PENALTY = 2
TINY_FRAGMENT_LENGTH = 3
TINY_FRAGMENT_PENALTY = 2


def _is_standalone_markdown_citation(text: str) -> bool:
    """
    Check if text appears to be a standalone markdown citation reference.

    Pattern: [[digits]](#footnote-digits)
    """
    stripped = text.strip()
    return bool(re.match(r"^\[\[\d+\]\]\(#footnote-\d+\)$", stripped))


def detect_by_reconstruction_quality(
    sentences: List[str], original_paragraph: str
) -> tuple[bool, int]:
    """
    Detect suspicious fragments by analyzing fragment characteristics.

    Universal: Works for ALL text types (citations, prose, technical, etc.)
    Performance: Very fast (~1-2ms, no external calls)
    Cost: Free

    Args:
        sentences: List of tokenized sentence fragments
        original_paragraph: The original paragraph before tokenization

    Returns:
        Tuple of (is_suspicious, suspicion_score)
    """
    filtered = _filter_empty_sentences(sentences)

    if len(filtered) == 1 and _is_standalone_markdown_citation(filtered[0]):
        return (True, SUSPICION_THRESHOLD)

    if len(filtered) <= 1:
        return (False, 0)

    stats = _calculate_fragment_stats(filtered)
    if not stats:
        return (False, 0)

    suspicion_score = _score_fragment_lengths(stats)

    # Check coefficient of variation for uneven splitting
    if len(stats["lengths"]) >= MIN_FRAGMENTS_FOR_CV:
        variance = sum((l - stats["avg_length"]) ** 2 for l in stats["lengths"]) / len(
            stats["lengths"]
        )
        std_dev = variance**0.5

        if stats["avg_length"] > 0:
            cv = std_dev / stats["avg_length"]
            if (
                cv > COEFFICIENT_OF_VARIATION_THRESHOLD
                and stats["min_length"] < SUSPICIOUS_FRAGMENT_LENGTH
            ):
                suspicion_score += HIGH_CV_PENALTY

    # Check for specific suspicious patterns
    for sentence in filtered:
        if (
            len(sentence) < VERY_SHORT_FRAGMENT_LENGTH
            and sentence.startswith("(")
            and sentence.endswith(").")
        ):
            suspicion_score += PARENTHETICAL_FRAGMENT_PENALTY

        if len(sentence) <= TINY_FRAGMENT_LENGTH and sentence.endswith("."):
            suspicion_score += TINY_FRAGMENT_PENALTY

        # Check if sentence is or starts with markdown citation - highly suspicious
        if _is_standalone_markdown_citation(sentence) or sentence.strip().startswith(
            "[["
        ):
            suspicion_score += (
                SUSPICION_THRESHOLD  # Auto-trigger for markdown citations
            )

        # Detect sentences starting with non-alphanumeric characters (likely formatting/citations)
        # This catches markdown syntax, citations, and other markup that was split incorrectly
        if len(sentence) > 0:
            first_char = sentence[0]
            # If sentence starts with special characters (not letter, digit, or quote)
            if not first_char.isalnum() and first_char not in "\"'":
                # Count leading special characters
                leading_special = 0
                for char in sentence:
                    if not char.isalnum() and not char.isspace():
                        leading_special += 1
                    else:
                        break

                # If significant portion starts with special chars, it's suspicious
                if leading_special >= 2:  # e.g., [[, **, ##, etc.
                    suspicion_score += SHORT_FRAGMENT_PENALTY

    return (suspicion_score >= SUSPICION_THRESHOLD, suspicion_score)


# Semantic coherence detection constants
SHORT_SENTENCE_THRESHOLD = 20
VERY_SHORT_SENTENCE_THRESHOLD = 30
HIGH_SIMILARITY_THRESHOLD = 0.95
VERY_HIGH_SIMILARITY_THRESHOLD = 0.98
SHORT_HIGH_SIMILARITY_PENALTY = 3
HIGH_SIMILARITY_PENALTY = 2


async def detect_by_semantic_coherence(
    sentences: List[str], original_paragraph: Optional[str] = None
) -> tuple[bool, int]:
    """
    Detect suspicious fragments using semantic coherence analysis with embeddings.

    Universal: Understands meaning, not just patterns
    Performance: Medium (~50-100ms due to embedding API calls)
    Cost: ~$0.0001 per check (uses text-embedding-3-small)

    Args:
        sentences: List of tokenized sentence fragments
        original_paragraph: The original paragraph (optional, not used in this method)

    Returns:
        Tuple of (is_suspicious, suspicion_score)
    """
    filtered = _filter_empty_sentences(sentences)
    if len(filtered) <= 1:
        return (False, 0)

    from lib.config.llm_models import init_embeddings

    suspicion_score = 0

    embeddings = init_embeddings()

    try:
        embedded = await embeddings.aembed_documents(filtered)
    except Exception:
        return detect_by_reconstruction_quality(filtered, original_paragraph or "")

    for i, sentence in enumerate(filtered):
        emb = np.array(embedded[i])

        if len(sentence) < SHORT_SENTENCE_THRESHOLD:
            suspicion_score += SHORT_FRAGMENT_PENALTY

        if i > 0:
            prev_emb = np.array(embedded[i - 1])
            dot_product = np.dot(emb, prev_emb)
            norm_product = np.linalg.norm(emb) * np.linalg.norm(prev_emb)

            if norm_product > 0:
                similarity = dot_product / norm_product

                # High similarity suggests they were one sentence split incorrectly
                if (
                    similarity > HIGH_SIMILARITY_THRESHOLD
                    and len(sentence) < VERY_SHORT_SENTENCE_THRESHOLD
                ):
                    suspicion_score += SHORT_HIGH_SIMILARITY_PENALTY
                elif similarity > VERY_HIGH_SIMILARITY_THRESHOLD:
                    suspicion_score += HIGH_SIMILARITY_PENALTY

    very_short_count = sum(1 for s in filtered if len(s) < MIN_FRAGMENT_LENGTH)
    if very_short_count >= 2:
        suspicion_score += VERY_SHORT_MULTIPLE_PENALTY

    return (suspicion_score >= SUSPICION_THRESHOLD, suspicion_score)


# Statistical anomaly detection constants
SINGLE_WORD_THRESHOLD = 2
ALPHANUMERIC_RATIO_THRESHOLD = 0.4
LOW_ALPHANUMERIC_PENALTY = 2


def detect_by_statistical_anomalies(
    sentences: List[str], original_paragraph: Optional[str] = None
) -> tuple[bool, int]:
    """
    Detect suspicious fragments using statistical anomaly detection.

    Universal: Based on fundamental sentence properties
    Performance: Very fast (<1ms, pure math)
    Cost: Free

    Args:
        sentences: List of tokenized sentence fragments
        original_paragraph: The original paragraph (optional, not used in this method)

    Returns:
        Tuple of (is_suspicious, suspicion_score)
    """
    filtered = _filter_empty_sentences(sentences)
    if len(filtered) <= 1:
        return (False, 0)

    stats = _calculate_fragment_stats(filtered)
    if not stats:
        return (False, 0)

    suspicion_score = _score_fragment_lengths(stats)

    word_counts = [len(s.split()) for s in filtered]

    # High coefficient of variation indicates inconsistent splitting
    if len(stats["lengths"]) > 1:
        std_length = np.std(stats["lengths"])
        if std_length > 0 and stats["avg_length"] > 0:
            cv = std_length / stats["avg_length"]
            if (
                cv > COEFFICIENT_OF_VARIATION_THRESHOLD
                and stats["min_length"] < SUSPICIOUS_FRAGMENT_LENGTH
            ):
                suspicion_score += HIGH_CV_PENALTY

    # Multiple single-word fragments
    single_word_count = sum(1 for wc in word_counts if wc <= SINGLE_WORD_THRESHOLD)
    if single_word_count >= 2:
        suspicion_score += VERY_SHORT_MULTIPLE_PENALTY

    # Fragment with only punctuation/numbers
    for sentence in filtered:
        alphanumeric = sum(c.isalnum() for c in sentence)
        if alphanumeric / len(sentence) < ALPHANUMERIC_RATIO_THRESHOLD:
            suspicion_score += LOW_ALPHANUMERIC_PENALTY
            break

    return (suspicion_score >= SUSPICION_THRESHOLD, suspicion_score)


async def has_suspicious_fragments(
    sentences: List[str],
    original_paragraph: str = "",
    method: DetectionMethod = "reconstruction",
) -> tuple[bool, int]:
    """
    Detect if sentence tokenization produced suspicious fragments.

    This is the main entry point. Select detection method via 'method' parameter.

    Args:
        sentences: List of tokenized sentence fragments
        original_paragraph: Original paragraph before tokenization
        method: Detection method to use:
            - "reconstruction": Fast, universal, based on fragment analysis
            - "semantic": Uses embeddings, most sophisticated but slower/costs money
            - "statistical": Fast, based on statistical anomalies

    Returns:
        Tuple of (is_suspicious, suspicion_score) where:
        - is_suspicious: True if fragments trigger LLM fallback, False otherwise
        - suspicion_score: The calculated suspicion score (higher = more suspicious)
    """
    if method == "reconstruction":
        return detect_by_reconstruction_quality(sentences, original_paragraph)
    elif method == "semantic":
        return await detect_by_semantic_coherence(sentences, original_paragraph)
    elif method == "statistical":
        return detect_by_statistical_anomalies(sentences, original_paragraph)
    else:
        raise ValueError(
            f"Invalid detection method: {method}. Must be one of: 'reconstruction', 'semantic', 'statistical'"
        )
