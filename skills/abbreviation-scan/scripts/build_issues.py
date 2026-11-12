"""Turn an abbreviation catalogue into abbreviation-scan issues.

Applies the five compliance rules of the abbreviation-scan skill to the
catalogue the abbreviation-extraction skill produces. Standard library only,
so it runs wherever Python 3.11+ does.

Usage:
    python build_issues.py catalogue.json        # or the JSON on stdin

Input (JSON):
    {
      "abbreviations_section_found": true,
      "occurrences": [
        {
          "abbr": "NATO",
          "inline_definition": "North Atlantic Treaty Organization",
          "occurrence_number": 1,
          "line_start": 12,
          "line_end": 12,
          "abbreviations_section_definition": "North Atlantic Treaty Organization"
        }
      ]
    }

Fields:
    abbreviations_section_found       Whether the document has an Abbreviations
                                      (or Acronyms, Glossary) section.
    occurrences                       Every place an abbreviation is used, in
                                      any order. Each one has:
      abbr                            The abbreviation, in singular form.
      inline_definition               The full name written next to it at this
                                      place, as in "North Atlantic Treaty
                                      Organization (NATO)". Use "" when it is
                                      used on its own.
      occurrence_number               1 for its first use in the document, 2 for
                                      the second, and so on.
      line_start, line_end            The document lines it is on.
      abbreviations_section_definition
                                      The full name the Abbreviations section
                                      gives it. Use null when the section does
                                      not list it, or there is no section.
      ignored (optional)              true to skip this use in every rule.

Output (JSON, on stdout): a list of issues, each with `title`, `description`,
`severity`, `start_line` and `end_line`. "No Abbreviations section found" is
not tied to any line, so it gets line 1 for both.
"""

from __future__ import annotations

import json
import re
import sys
from typing import NotRequired, TypedDict

SEVERITY = "medium"
MATCH_THRESHOLD = 85.0

NO_SECTION = "No Abbreviations section found"
NOT_DEFINED = "Abbreviation not defined at first use"
MISSING_FROM_SECTION = "Abbreviation missing from Abbreviations section"
DEFINITION_MISMATCH = "Inline definition does not match Abbreviations section"
AMBIGUOUS = "Ambiguous abbreviation"


class Occurrence(TypedDict):
    abbr: str
    inline_definition: str
    occurrence_number: int
    line_start: int
    line_end: int
    abbreviations_section_definition: str | None
    ignored: NotRequired[bool]


class Issue(TypedDict):
    title: str
    description: str
    severity: str
    start_line: int | None
    end_line: int | None
    occurrence_index: int | None
    """Position in the input list of the occurrence the issue is located at."""


def build_issues(
    occurrences: list[Occurrence], abbreviations_section_found: bool
) -> list[Issue]:
    """Every genuine problem, each reported at most once per abbreviation.

    The catalogue is per occurrence (a long document yields hundreds of
    entries), but a reader does not need to be told forty times that the same
    abbreviation is missing from the Abbreviations section.
    """
    # Excluded occurrences are out of scope for every rule.
    in_scope = [
        (index, occ)
        for index, occ in enumerate(occurrences)
        if not occ.get("ignored", False)
    ]
    if not in_scope:
        return []

    issues: list[Issue] = []
    if not abbreviations_section_found:
        issues.append(_issue(NO_SECTION, _no_section_description(), None, None))

    first = _first_occurrence_per_abbr(in_scope)
    for abbr in sorted(first):
        index, occ = first[abbr]
        issues.extend(_first_use_issues(index, occ, abbreviations_section_found))

    issues.extend(_ambiguity_issues(in_scope))
    return issues


def _first_occurrence_per_abbr(
    items: list[tuple[int, Occurrence]],
) -> dict[str, tuple[int, Occurrence]]:
    """Map each abbreviation to the occurrence the rules treat as its first use."""
    first: dict[str, tuple[int, Occurrence]] = {}
    for index, occ in items:
        current = first.get(occ["abbr"])
        if (
            current is None
            or occ["occurrence_number"] < current[1]["occurrence_number"]
        ):
            first[occ["abbr"]] = (index, occ)
    return first


def _first_use_issues(index: int, occ: Occurrence, section_found: bool) -> list[Issue]:
    """Rules 2–4, all judged at the abbreviation's first occurrence."""
    abbr, inline = occ["abbr"], occ["inline_definition"]
    listed = occ["abbreviations_section_definition"]
    issues: list[Issue] = []

    if not inline:
        description = (
            f'The abbreviation "{abbr}" is used without an inline definition at '
            f'its first occurrence. It should be introduced as "Full Name ({abbr})" '
            f"the first time it appears."
        )
        issues.append(_issue(NOT_DEFINED, description, index, occ))

    if section_found and listed is None:
        description = (
            f'The abbreviation "{abbr}" is used in the document but is not listed '
            f"in the Abbreviations section."
        )
        issues.append(_issue(MISSING_FROM_SECTION, description, index, occ))

    if inline and listed is not None and not text_matches(inline, listed):
        description = (
            f'The inline definition for "{abbr}" — "{inline}" — differs from the '
            f'entry in the Abbreviations section: "{listed}".'
        )
        issues.append(_issue(DEFINITION_MISMATCH, description, index, occ))

    return issues


def _ambiguity_issues(items: list[tuple[int, Occurrence]]) -> list[Issue]:
    """Rule 5: the same abbreviation given two different inline definitions.

    The baseline is the earliest occurrence that actually carries a definition:
    an abbreviation used bare before it is ever defined still establishes its
    meaning there. Reported once per abbreviation, at the first conflict.
    """
    issues: list[Issue] = []
    established: dict[str, str] = {}
    flagged: set[str] = set()

    ordered = sorted(
        items, key=lambda pair: (pair[1]["occurrence_number"], pair[1]["line_start"])
    )
    for index, occ in ordered:
        abbr, inline = occ["abbr"], occ["inline_definition"]
        if not inline:
            continue
        prior = established.get(abbr)
        if prior is None:
            established[abbr] = inline
            continue
        if abbr in flagged or text_matches(inline, prior):
            continue
        flagged.add(abbr)
        description = (
            f'The abbreviation "{abbr}" is defined here as "{inline}" but was '
            f'previously defined as "{prior}". Avoid using the same abbreviation '
            f"to mean more than one thing in the same document."
        )
        issues.append(_issue(AMBIGUOUS, description, index, occ))

    return issues


def _no_section_description() -> str:
    return (
        "The document uses abbreviations but does not contain a dedicated "
        '"Abbreviations", "Acronyms", or equivalent section. '
        "All abbreviations should be listed in such a section."
    )


def _issue(
    title: str, description: str, index: int | None, occ: Occurrence | None
) -> Issue:
    return Issue(
        title=title,
        description=description,
        severity=SEVERITY,
        start_line=occ["line_start"] if occ else None,
        end_line=occ["line_end"] if occ else None,
        occurrence_index=index,
    )


# --- Fuzzy matching ------------------------------------------------------------
# A stdlib port of rapidfuzz's `fuzz.partial_ratio` with `utils.default_process`
# (rapidfuzz 3.x, MIT, Max Bachmann), so definitions that differ only in case,
# punctuation or a trailing word ("the Office of X" / "Office of X") still match.
# Scores equal rapidfuzz's exactly; the only differences are in how a few rare
# scripts are classed as letters, where Python's Unicode tables and rapidfuzz's
# disagree. Latin, Greek, Cyrillic and common punctuation all agree.

# Underscore counts as punctuation, as in rapidfuzz's compiled implementation.
_NON_ALNUM_RE = re.compile(r"[\W_]")


def text_matches(a: str, b: str, threshold: float = MATCH_THRESHOLD) -> bool:
    """Whether two definitions say the same thing, ignoring trivial differences."""
    if not a or not b:
        return False
    return partial_ratio(_default_process(a), _default_process(b)) >= threshold


def _default_process(text: str) -> str:
    # Lowercased one character at a time, as rapidfuzz does: `str.lower()` on
    # the whole string would apply the Greek final-sigma rule ("ΟΣ" -> "ος").
    # Taking the first code point keeps "İ" a plain "i", its simple mapping.
    return "".join(ch.lower()[0] for ch in _NON_ALNUM_RE.sub(" ", text).strip())


def partial_ratio(s1: str, s2: str) -> float:
    """Best similarity (0–100) of the shorter string against any window of the longer."""
    if not s1 and not s2:
        return 100.0
    shorter, longer = (s1, s2) if len(s1) <= len(s2) else (s2, s1)
    # Some window then equals the shorter string exactly: the best score there is.
    if shorter and shorter in longer:
        return 100.0
    score = _partial_ratio_impl(shorter, longer)
    if score != 100 and len(s1) == len(s2):
        score = max(score, _partial_ratio_impl(longer, shorter))
    return score


def _partial_ratio_impl(s1: str, s2: str) -> float:
    """Slide `s1` over `s2` (len(s1) <= len(s2)), as rapidfuzz does."""
    chars = set(s1)
    len1, len2 = len(s1), len(s2)
    windows = (
        [s2[:i] for i in range(1, len1) if s2[i - 1] in chars]
        + [s2[i : i + len1] for i in range(len2 - len1) if s2[i + len1 - 1] in chars]
        + [s2[i:] for i in range(len2 - len1, len2) if s2[i] in chars]
    )
    block = _match_masks(s1)
    best = 0.0
    for window in windows:
        # 1 - Indel distance / total length, written as rapidfuzz computes it
        # so the floats agree exactly at the threshold.
        lensum = len1 + len(window)
        distance = lensum - 2 * _lcs_length(block, len1, window)
        similarity = 1.0 - distance / lensum
        best = max(best, similarity)
        if best == 1:
            return 100.0
    return best * 100


def _match_masks(s1: str) -> dict[str, int]:
    """For each character of `s1`, a bit mask of the positions it sits at."""
    block: dict[str, int] = {}
    for position, ch in enumerate(s1):
        block[ch] = block.get(ch, 0) | (1 << position)
    return block


def _lcs_length(block: dict[str, int], len1: int, s2: str) -> int:
    """Longest common subsequence of `s1` (given as its masks) and `s2`.

    Hyyrö's bit-parallel algorithm, the one rapidfuzz uses: each character of
    `s2` costs a few integer operations rather than a pass over `s1`, so a
    window costs about len(s2) operations instead of len(s1) * len(s2).
    """
    mask = (1 << len1) - 1
    v = mask
    for ch in s2:
        u = v & block.get(ch, 0)
        v = ((v + u) | (v - u)) & mask
    return len1 - v.bit_count()


# --- Command line ----------------------------------------------------------------


def main(argv: list[str]) -> int:
    source = open(argv[1], encoding="utf-8") if len(argv) > 1 else sys.stdin
    with source:
        data = json.load(source)
    issues = build_issues(
        data.get("occurrences", []), bool(data.get("abbreviations_section_found"))
    )
    output = [
        {
            "title": issue["title"],
            "description": issue["description"],
            "severity": issue["severity"],
            "start_line": issue["start_line"] or 1,
            "end_line": issue["end_line"] or 1,
        }
        for issue in issues
    ]
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
