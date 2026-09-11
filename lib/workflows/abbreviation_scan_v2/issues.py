"""Convert abbreviation scan v2 state into document issues.

Only genuine problems are reported, and each one at most once per abbreviation.
The catalogue in state is per-occurrence — a long document yields hundreds of
entries — but a reader does not need to be told the same abbreviation is missing
from the Abbreviations section forty times, nor that the other forty passed.
"""

from typing import Dict, List

from lib.services.text_matching import text_matches
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationItem,
    AbbreviationScanV2State,
)
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType

_WORKFLOW_TYPE = WorkflowRunType.ABBREVIATION_SCAN_V2


def build_issues(state: AbbreviationScanV2State) -> List[DocumentIssue]:
    """Build the full list of document issues from the abbreviation scan state."""

    if not state.abbreviations:
        return []

    # Excluded occurrences are out of scope for every rule, so they never reach
    # the rule checks and never produce an issue of their own.
    in_scope = [item for item in state.abbreviations if not item.ignored]
    if not in_scope:
        return []

    first_occurrence = _first_occurrence_per_abbr(in_scope)

    issues: List[DocumentIssue] = []

    if not state.abbreviations_section_found:
        issues.append(_no_abbreviations_section_issue())

    for abbr in sorted(first_occurrence):
        first = first_occurrence[abbr]

        if not first.inline_definition:
            issues.append(_not_defined_at_first_use_issue(first))

        if (
            state.abbreviations_section_found
            and first.abbreviations_section_definition is None
        ):
            issues.append(_missing_from_section_issue(first))

        if (
            first.inline_definition
            and first.abbreviations_section_definition is not None
            and not text_matches(
                first.inline_definition, first.abbreviations_section_definition
            )
        ):
            issues.append(_definition_mismatch_issue(first))

    issues.extend(_ambiguity_issues(in_scope, first_occurrence))
    return issues


def _first_occurrence_per_abbr(
    items: List[AbbreviationItem],
) -> Dict[str, AbbreviationItem]:
    """Map each abbreviation to the occurrence the rules treat as its first use."""
    first: Dict[str, AbbreviationItem] = {}
    for item in items:
        current = first.get(item.abbr)
        if current is None or item.occurrence_number < current.occurrence_number:
            first[item.abbr] = item
    return first


def _ambiguity_issues(
    items: List[AbbreviationItem],
    first_occurrence: Dict[str, AbbreviationItem],
) -> List[DocumentIssue]:
    """Rule 5 — the same abbreviation given two different inline definitions.

    Reported at the conflicting occurrence, and only once per abbreviation: a
    document that redefines a term repeatedly needs one flag, not one per use.
    """
    issues: List[DocumentIssue] = []
    established: Dict[str, str] = {
        abbr: item.inline_definition
        for abbr, item in first_occurrence.items()
        if item.inline_definition
    }
    already_flagged: set[str] = set()

    for item in items:
        prior = established.get(item.abbr)
        if (
            not item.inline_definition
            or prior is None
            or item.abbr in already_flagged
            or text_matches(item.inline_definition, prior)
        ):
            continue
        already_flagged.add(item.abbr)
        issues.append(_ambiguous_issue(item, prior))

    return issues


def _no_abbreviations_section_issue() -> DocumentIssue:
    return DocumentIssue(
        title="No Abbreviations section found",
        description=(
            "The document uses abbreviations but does not contain a dedicated "
            '"Abbreviations", "Acronyms", or equivalent section. '
            "All abbreviations should be listed in such a section."
        ),
        severity=SeverityEnum.MEDIUM,
        type=_WORKFLOW_TYPE,
    )


def _not_defined_at_first_use_issue(item: AbbreviationItem) -> DocumentIssue:
    return DocumentIssue(
        title="Abbreviation not defined at first use",
        description=(
            f'The abbreviation "{item.abbr}" is used without an inline '
            f"definition at its first occurrence. It should be introduced as "
            f'"Full Name ({item.abbr})" the first time it appears.'
        ),
        severity=SeverityEnum.MEDIUM,
        type=_WORKFLOW_TYPE,
        start_line=item.line_start,
        end_line=item.line_end,
    )


def _missing_from_section_issue(item: AbbreviationItem) -> DocumentIssue:
    return DocumentIssue(
        title="Abbreviation missing from Abbreviations section",
        description=(
            f'The abbreviation "{item.abbr}" is used in the document but is not '
            f"listed in the Abbreviations section."
        ),
        severity=SeverityEnum.MEDIUM,
        type=_WORKFLOW_TYPE,
        start_line=item.line_start,
        end_line=item.line_end,
    )


def _definition_mismatch_issue(item: AbbreviationItem) -> DocumentIssue:
    return DocumentIssue(
        title="Inline definition does not match Abbreviations section",
        description=(
            f'The inline definition for "{item.abbr}" — '
            f'"{item.inline_definition}" — differs from the entry in '
            f"the Abbreviations section: "
            f'"{item.abbreviations_section_definition}".'
        ),
        severity=SeverityEnum.MEDIUM,
        type=_WORKFLOW_TYPE,
        start_line=item.line_start,
        end_line=item.line_end,
    )


def _ambiguous_issue(item: AbbreviationItem, prior_definition: str) -> DocumentIssue:
    return DocumentIssue(
        title="Ambiguous abbreviation",
        description=(
            f'The abbreviation "{item.abbr}" is defined here as '
            f'"{item.inline_definition}" but was previously defined as '
            f'"{prior_definition}". Avoid using the same abbreviation to mean '
            f"more than one thing in the same document."
        ),
        severity=SeverityEnum.MEDIUM,
        type=_WORKFLOW_TYPE,
        start_line=item.line_start,
        end_line=item.line_end,
    )
