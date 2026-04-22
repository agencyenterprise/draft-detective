"""Convert abbreviation scan v2 state into document issues."""

from typing import List

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

    issues: List[DocumentIssue] = []

    has_non_ignored = any(not item.ignored for item in state.abbreviations)
    if not state.abbreviations_section_found and has_non_ignored:
        issues.append(_no_abbreviations_section_issue())

    first_non_ignored = _first_non_ignored_occurrence(state.abbreviations)
    first_definition = _first_inline_definitions(state.abbreviations)

    for item in state.abbreviations:
        if item.ignored:
            issues.append(_ignored_issue(item))
            continue

        issues.extend(
            _section_coverage_issues(item, state.abbreviations_section_found)
        )
        issues.extend(_inline_definition_issues(item, first_non_ignored))
        issues.extend(_ambiguity_issues(item, first_definition))

    return issues


def _first_non_ignored_occurrence(
    items: List[AbbreviationItem],
) -> dict[str, int]:
    """Map each abbreviation to its first non-ignored occurrence number."""
    result: dict[str, int] = {}
    for item in items:
        if not item.ignored and item.abbr not in result:
            result[item.abbr] = item.occurrence_number
    return result


def _first_inline_definitions(
    items: List[AbbreviationItem],
) -> dict[str, str]:
    """Map each abbreviation to the first inline definition seen (non-ignored)."""
    result: dict[str, str] = {}
    for item in items:
        if not item.ignored and item.inline_definition:
            result.setdefault(item.abbr, item.inline_definition)
    return result


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


def _ignored_issue(item: AbbreviationItem) -> DocumentIssue:
    return DocumentIssue(
        title=f'"{item.abbr}" ignored',
        description=(
            f'Occurrence #{item.occurrence_number} of "{item.abbr}" '
            f"was ignored. Reason: {item.ignored_reason or 'Excluded from compliance checks.'}"
        ),
        severity=SeverityEnum.NONE,
        type=_WORKFLOW_TYPE,
        start_line=item.line_start,
        end_line=item.line_end,
    )


def _section_coverage_issues(
    item: AbbreviationItem,
    abbreviations_section_found: bool,
) -> List[DocumentIssue]:
    if not abbreviations_section_found:
        return []

    if item.abbreviations_section_definition is None:
        return [
            DocumentIssue(
                title="Abbreviation missing from Abbreviations section",
                description=(
                    f'Occurrence #{item.occurrence_number} of "{item.abbr}" — '
                    f"this abbreviation is not listed in the Abbreviations section."
                ),
                severity=SeverityEnum.MEDIUM,
                type=_WORKFLOW_TYPE,
                start_line=item.line_start,
                end_line=item.line_end,
            )
        ]

    return [
        DocumentIssue(
            title="Abbreviation defined in Abbreviations section",
            description=(
                f'Occurrence #{item.occurrence_number} of "{item.abbr}" — '
                f"this abbreviation is listed in the Abbreviations section as "
                f'"{item.abbreviations_section_definition}".'
            ),
            severity=SeverityEnum.NONE,
            type=_WORKFLOW_TYPE,
            start_line=item.line_start,
            end_line=item.line_end,
        )
    ]


def _inline_definition_issues(
    item: AbbreviationItem,
    first_non_ignored: dict[str, int],
) -> List[DocumentIssue]:
    if item.occurrence_number != first_non_ignored.get(item.abbr):
        return [
            DocumentIssue(
                title=f'"{item.abbr}" occurrence #{item.occurrence_number}',
                description=(
                    f'Occurrence #{item.occurrence_number} of "{item.abbr}" — '
                    f"no inline definition needed at subsequent uses."
                ),
                severity=SeverityEnum.NONE,
                type=_WORKFLOW_TYPE,
                start_line=item.line_start,
                end_line=item.line_end,
            )
        ]

    if not item.inline_definition:
        return [
            DocumentIssue(
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
        ]

    if item.abbreviations_section_definition is not None and not text_matches(
        item.inline_definition, item.abbreviations_section_definition
    ):
        return [
            DocumentIssue(
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
        ]

    return [
        DocumentIssue(
            title=f'"{item.abbr}" correctly defined at first use',
            description=(
                f'The abbreviation "{item.abbr}" is correctly introduced as '
                f'"{item.inline_definition} ({item.abbr})" at its first occurrence.'
            ),
            severity=SeverityEnum.NONE,
            type=_WORKFLOW_TYPE,
            start_line=item.line_start,
            end_line=item.line_end,
        )
    ]


def _ambiguity_issues(
    item: AbbreviationItem,
    first_definition: dict[str, str],
) -> List[DocumentIssue]:
    prior_def = first_definition.get(item.abbr)
    if (
        item.inline_definition
        and prior_def
        and not text_matches(item.inline_definition, prior_def)
    ):
        return [
            DocumentIssue(
                title="Ambiguous abbreviation",
                description=(
                    f'The abbreviation "{item.abbr}" is defined here as '
                    f'"{item.inline_definition}" but was previously defined as '
                    f'"{prior_def}". Avoid using the same abbreviation to mean '
                    f"more than one thing in the same document."
                ),
                severity=SeverityEnum.MEDIUM,
                type=_WORKFLOW_TYPE,
                start_line=item.line_start,
                end_line=item.line_end,
            )
        ]
    return []
