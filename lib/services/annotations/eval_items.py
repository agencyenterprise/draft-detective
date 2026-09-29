"""Annotation items built from an issue-inventory eval dataset.

Every anchored expected issue becomes a "should be flagged" item and every
decoy a "should be left alone" one, so annotators judge the same passages the
eval scores. The dataset is read with the evals' own loader, so anchors resolve
exactly as they do for the scorers.
"""

import hashlib
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from evals_inspectai.common.issue_inventory import (
    Decoy,
    ResolvedInventory,
    ResolvedIssue,
    load_inventory_records,
    normalize,
)
from lib.models.annotation import AnnotationItemKind
from lib.services.annotations.catalog import SHOULD_FLAG, AnnotationSetSpec
from lib.services.annotations.models import AnnotationPassage


class AnnotationItemDraft(BaseModel):
    """An item as the dataset defines it, before it is written to the database."""

    source_key: str
    kind: AnnotationItemKind
    passage: AnnotationPassage
    reference_answers: dict[str, str]
    reference_explanation: Optional[str]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _source_key(document: str, anchor: str, kind: AnnotationItemKind) -> str:
    """Content-addressed: editing the document or the passage makes a new item."""
    return f"{_digest(document)}:{_digest(normalize(anchor))}:{kind.value}"


def _line_of(document: str, anchor: str) -> Optional[int]:
    target = normalize(anchor)
    for number, line in enumerate(document.split("\n"), 1):
        if target in normalize(line):
            return number
    return None


def _issue_item(
    record: ResolvedInventory, issue: ResolvedIssue
) -> Optional[AnnotationItemDraft]:
    # An issue about something absent has no passage to show, and an optional
    # one is borderline by design, so neither answer is the dataset's.
    if issue.anchor is None or not issue.required:
        return None
    kind = AnnotationItemKind.EXPECTED_ISSUE
    explanation = (
        f"Our test case expects Draft Detective to flag this as “{issue.title}”."
        if issue.title
        else "Our test case expects Draft Detective to flag this."
    )
    return AnnotationItemDraft(
        source_key=_source_key(record.document, issue.anchor, kind),
        kind=kind,
        passage=AnnotationPassage(
            document=record.document, anchor=issue.anchor, line=issue.line
        ),
        reference_answers={SHOULD_FLAG: "yes"},
        reference_explanation=explanation,
    )


def _decoy_item(
    record: ResolvedInventory, decoy: Decoy, spec: AnnotationSetSpec
) -> Optional[AnnotationItemDraft]:
    # A titled decoy may rightly be reported under another kind, so "should it
    # be flagged at all?" has no single answer.
    if decoy.title is not None:
        return None
    kind = AnnotationItemKind.DECOY
    reason = spec.decoy_reasons.get(decoy.reason, decoy.reason.replace("_", " "))
    return AnnotationItemDraft(
        source_key=_source_key(record.document, decoy.anchor, kind),
        kind=kind,
        passage=AnnotationPassage(
            document=record.document,
            anchor=decoy.anchor,
            line=_line_of(record.document, decoy.anchor),
        ),
        reference_answers={SHOULD_FLAG: "no"},
        reference_explanation=f"Our test case expects Draft Detective to leave this alone: {reason}.",
    )


def items_from_inventory(
    spec: AnnotationSetSpec, path: Optional[Path] = None
) -> list[AnnotationItemDraft]:
    """One item per anchored passage in the dataset, deduplicated by source key."""
    drafts: dict[str, AnnotationItemDraft] = {}
    for record in load_inventory_records(path or spec.dataset_path):
        candidates = [_issue_item(record, issue) for issue in record.expected_issues]
        candidates += [_decoy_item(record, decoy, spec) for decoy in record.decoys]
        for draft in candidates:
            if draft is not None:
                drafts.setdefault(draft.source_key, draft)
    return list(drafts.values())
