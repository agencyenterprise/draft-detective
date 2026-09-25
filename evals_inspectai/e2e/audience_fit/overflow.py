"""Audience Fit's own deterministic check: the cap on technical-language issues.

The skill reports up to ``CAP`` paragraph-level ``Technical Language`` issues,
keeps the first ``CAP`` in document order, and puts the rest in one
``Technical Language: Further Paragraphs`` summary. The inventory detection
checks cannot see that shape: an eighteenth paragraph reported on its own, or
dropped, or a summary under the wrong title, all still detect the expected
issues. These checks score it directly, on a sample whose inventory expects
more than ``CAP`` technical paragraphs; every other sample is NaN. They ask
for at most ``CAP`` issues titled exactly ``Technical Language``, one of them
for each of the first ``CAP`` technical paragraphs in document order and none
for a paragraph past the cap, exactly one summary at ``low`` severity, and a
summary that spans every remaining paragraph and quotes each one's term.
Whether the summary gives each paragraph a plain alternative is graded in
``overflow_judge``.
"""

import math
from typing import Optional, Sequence

from evals_inspectai.common.issue_inventory import (
    AnchoredIssue,
    ResolvedInventory,
    anchored,
    normalize,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem

CAP = 15
PARAGRAPH_TITLE = "Technical Language"
SUMMARY_TITLE = "Technical Language: Further Paragraphs"
SUMMARY_SEVERITY = "low"

OVERFLOW_KEYS = (
    "overflow_cap",
    "overflow_first_in_order",
    "overflow_summary_title",
    "overflow_summary_covers_rest",
)
OVERFLOW_DESCRIPTIONS = {
    "overflow_cap": f"On a sample with more than {CAP} technical paragraphs: at most {CAP} issues titled exactly '{PARAGRAPH_TITLE}'.",
    "overflow_first_in_order": f"On that sample: each of the first {CAP} technical paragraphs in document order has its own '{PARAGRAPH_TITLE}' issue (matched one-to-one), and no such issue covers a paragraph past the cap.",
    "overflow_summary_title": f"On that sample: exactly one issue titled '{SUMMARY_TITLE}', with severity {SUMMARY_SEVERITY}.",
    "overflow_summary_covers_rest": "On that sample: the summary spans every remaining technical paragraph and quotes each one's term.",
}
OVERFLOW_LABELS = {
    "overflow_cap": "Cap",
    "overflow_first_in_order": "First in order",
    "overflow_summary_title": "Summary title",
    "overflow_summary_covers_rest": "Summary covers rest",
}


def _text(issue: IssueItem) -> str:
    return normalize(
        " ".join(
            [
                issue.description,
                issue.long_description or "",
                issue.suggested_action or "",
            ]
        )
    )


def _covers(issue: IssueItem, expected: AnchoredIssue) -> bool:
    return (
        normalize(expected.anchor) in _text(issue)
        or issue.start_line <= expected.line <= issue.end_line
    )


def unmatched(
    paragraphs: Sequence[AnchoredIssue], singles: Sequence[IssueItem]
) -> list[AnchoredIssue]:
    """The paragraphs left without an issue of their own under a maximum one-to-one matching.

    Kuhn's augmenting paths: one broad issue covering several paragraphs can
    stand for only one of them.
    """
    owner: dict[int, int] = {}  # single issue index -> paragraph index

    def claim(p: int, seen: set[int]) -> bool:
        for s, issue in enumerate(singles):
            if s in seen or not _covers(issue, paragraphs[p]):
                continue
            seen.add(s)
            if s not in owner or claim(owner[s], seen):
                owner[s] = p
                return True
        return False

    return [e for p, e in enumerate(paragraphs) if not claim(p, set())]


def technical_paragraphs(inventory: ResolvedInventory) -> list[AnchoredIssue]:
    """The expected paragraph-level technical-language issues, in document order."""
    kept = [anchored(e) for e in inventory.expected_issues if e.title == PARAGRAPH_TITLE]
    return sorted(kept, key=lambda e: e.line)


def overflow_split(
    inventory: ResolvedInventory,
) -> Optional[tuple[list[AnchoredIssue], list[AnchoredIssue]]]:
    """The first ``CAP`` technical paragraphs and the rest; None unless the inventory expects more than ``CAP``."""
    expected = technical_paragraphs(inventory)
    return (expected[:CAP], expected[CAP:]) if len(expected) > CAP else None


def overflow_summaries(issues: Sequence[IssueItem]) -> list[IssueItem]:
    """The reported issues titled as the overflow summary."""
    return [i for i in issues if normalize(i.title) == normalize(SUMMARY_TITLE)]


def overflow_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory
) -> tuple[dict[str, float], str]:
    """The four overflow keys; NaN unless the inventory expects more than ``CAP`` technical paragraphs."""
    split = overflow_split(inventory)
    if split is None:
        return {key: math.nan for key in OVERFLOW_KEYS}, "not an overflow sample"
    first, rest = split
    singles = [i for i in issues if normalize(i.title) == normalize(PARAGRAPH_TITLE)]
    summaries = overflow_summaries(issues)
    missing = [e.id for e in unmatched(first, singles)]
    strays = [e.id for e in rest if any(_covers(i, e) for i in singles)]
    summary = summaries[0] if len(summaries) == 1 else None
    uncovered = [
        e.id
        for e in rest
        if summary is None
        or not (
            summary.start_line <= e.line <= summary.end_line
            and normalize(e.anchor) in _text(summary)
        )
    ]
    values = {
        "overflow_cap": float(len(singles) <= CAP),
        "overflow_first_in_order": float(not missing and not strays),
        "overflow_summary_title": float(
            summary is not None and summary.severity == SUMMARY_SEVERITY
        ),
        "overflow_summary_covers_rest": float(not uncovered),
    }
    notes = [f"{len(singles)} single issues, {len(summaries)} summaries"]
    if missing:
        notes.append("first paragraphs without their own issue: " + ", ".join(missing))
    if strays:
        notes.append(
            "paragraphs past the cap with a single issue: " + ", ".join(strays)
        )
    if uncovered:
        notes.append(
            "remaining paragraphs the summary does not cover: " + ", ".join(uncovered)
        )
    return values, " | ".join(notes)
