"""Tests for abbreviation scan v2 issue conversion logic."""

from typing import List, Optional

from lib.workflows.abbreviation_scan_v2.issues import (
    build_issues,
    _ambiguity_issues,
    _first_inline_definitions,
    _first_non_ignored_occurrence,
    _ignored_issue,
    _inline_definition_issues,
    _no_abbreviations_section_issue,
    _section_coverage_issues,
)
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationItem,
    AbbreviationScanV2Config,
    AbbreviationScanV2State,
)
from lib.workflows.models import SeverityEnum, WorkflowRunType


def _item(
    abbr: str = "AI",
    inline_definition: str = "",
    occurrence_number: int = 1,
    line_start: int = 1,
    line_end: int = 1,
    abbreviations_section_definition: Optional[str] = None,
    ignored: bool = False,
    ignored_reason: Optional[str] = None,
) -> AbbreviationItem:
    return AbbreviationItem(
        abbr=abbr,
        inline_definition=inline_definition,
        occurrence_number=occurrence_number,
        line_start=line_start,
        line_end=line_end,
        abbreviations_section_definition=abbreviations_section_definition,
        ignored=ignored,
        ignored_reason=ignored_reason,
    )


def _state(
    abbreviations: Optional[List[AbbreviationItem]] = None,
    abbreviations_section_found: bool = False,
) -> AbbreviationScanV2State:
    return AbbreviationScanV2State(
        type=WorkflowRunType.ABBREVIATION_SCAN_V2,
        config=AbbreviationScanV2Config(project_id="test-project"),
        abbreviations=abbreviations or [],
        abbreviations_section_found=abbreviations_section_found,
    )


# ---------------------------------------------------------------------------
# _first_non_ignored_occurrence
# ---------------------------------------------------------------------------


class TestFirstNonIgnoredOccurrence:
    def test_picks_first_non_ignored(self):
        items = [
            _item(abbr="AI", occurrence_number=1, ignored=True),
            _item(abbr="AI", occurrence_number=2),
            _item(abbr="AI", occurrence_number=3),
        ]
        assert _first_non_ignored_occurrence(items) == {"AI": 2}

    def test_multiple_abbreviations(self):
        items = [
            _item(abbr="AI", occurrence_number=1),
            _item(abbr="LLM", occurrence_number=1),
            _item(abbr="AI", occurrence_number=2),
        ]
        result = _first_non_ignored_occurrence(items)
        assert result == {"AI": 1, "LLM": 1}

    def test_all_ignored_returns_empty(self):
        items = [_item(abbr="AI", ignored=True, ignored_reason="exempt")]
        assert _first_non_ignored_occurrence(items) == {}

    def test_empty_list(self):
        assert _first_non_ignored_occurrence([]) == {}


# ---------------------------------------------------------------------------
# _first_inline_definitions
# ---------------------------------------------------------------------------


class TestFirstInlineDefinitions:
    def test_picks_first_definition(self):
        items = [
            _item(
                abbr="AI",
                inline_definition="Artificial Intelligence",
                occurrence_number=1,
            ),
            _item(abbr="AI", inline_definition="", occurrence_number=2),
        ]
        assert _first_inline_definitions(items) == {"AI": "Artificial Intelligence"}

    def test_ignores_ignored_items(self):
        items = [
            _item(
                abbr="AI",
                inline_definition="Artificial Intelligence",
                ignored=True,
                ignored_reason="heading",
            ),
            _item(
                abbr="AI",
                inline_definition="Artificial Intelligence",
                occurrence_number=2,
            ),
        ]
        assert _first_inline_definitions(items) == {"AI": "Artificial Intelligence"}

    def test_no_definitions(self):
        items = [_item(abbr="AI")]
        assert _first_inline_definitions(items) == {}


# ---------------------------------------------------------------------------
# _no_abbreviations_section_issue
# ---------------------------------------------------------------------------


class TestNoAbbreviationsSectionIssue:
    def test_creates_medium_severity_issue(self):
        issue = _no_abbreviations_section_issue()
        assert issue.severity == SeverityEnum.MEDIUM
        assert "No Abbreviations section found" in issue.title


# ---------------------------------------------------------------------------
# _ignored_issue
# ---------------------------------------------------------------------------


class TestIgnoredIssue:
    def test_creates_none_severity(self):
        item = _item(abbr="Mr.", ignored=True, ignored_reason="Personal title")
        issue = _ignored_issue(item)
        assert issue.severity == SeverityEnum.NONE
        assert '"Mr." ignored' in issue.title
        assert "Personal title" in issue.description

    def test_default_reason_when_none(self):
        item = _item(abbr="U.S.", ignored=True)
        issue = _ignored_issue(item)
        assert "Excluded from compliance checks." in issue.description


# ---------------------------------------------------------------------------
# _section_coverage_issues
# ---------------------------------------------------------------------------


class TestSectionCoverageIssues:
    def test_no_issues_when_section_not_found(self):
        item = _item(abbr="AI")
        assert (
            _section_coverage_issues(item, abbreviations_section_found=False) == []
        )

    def test_missing_from_section(self):
        item = _item(abbr="DDoS", abbreviations_section_definition=None)
        issues = _section_coverage_issues(item, abbreviations_section_found=True)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.MEDIUM
        assert "missing from Abbreviations section" in issues[0].title

    def test_present_in_section(self):
        item = _item(
            abbr="AI", abbreviations_section_definition="Artificial Intelligence"
        )
        issues = _section_coverage_issues(item, abbreviations_section_found=True)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.NONE
        assert "defined in Abbreviations section" in issues[0].title


# ---------------------------------------------------------------------------
# _inline_definition_issues
# ---------------------------------------------------------------------------


class TestInlineDefinitionIssues:
    def test_subsequent_occurrence_info_only(self):
        first_non_ignored = {"AI": 1}
        item = _item(abbr="AI", occurrence_number=2)
        issues = _inline_definition_issues(item, first_non_ignored)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.NONE
        assert "occurrence #2" in issues[0].title

    def test_first_use_missing_definition(self):
        first_non_ignored = {"AI": 1}
        item = _item(abbr="AI", occurrence_number=1, inline_definition="")
        issues = _inline_definition_issues(item, first_non_ignored)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.MEDIUM
        assert "not defined at first use" in issues[0].title

    def test_first_use_definition_matches_section(self):
        first_non_ignored = {"AI": 1}
        item = _item(
            abbr="AI",
            occurrence_number=1,
            inline_definition="Artificial Intelligence",
            abbreviations_section_definition="Artificial Intelligence",
        )
        issues = _inline_definition_issues(item, first_non_ignored)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.NONE
        assert "correctly defined at first use" in issues[0].title

    def test_first_use_definition_mismatches_section(self):
        first_non_ignored = {"AI": 1}
        item = _item(
            abbr="AI",
            occurrence_number=1,
            inline_definition="Advanced Imaging",
            abbreviations_section_definition="Artificial Intelligence",
        )
        issues = _inline_definition_issues(item, first_non_ignored)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.MEDIUM
        assert "does not match" in issues[0].title

    def test_first_use_defined_no_section(self):
        first_non_ignored = {"AI": 1}
        item = _item(
            abbr="AI",
            occurrence_number=1,
            inline_definition="Artificial Intelligence",
            abbreviations_section_definition=None,
        )
        issues = _inline_definition_issues(item, first_non_ignored)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.NONE
        assert "correctly defined" in issues[0].title


# ---------------------------------------------------------------------------
# _ambiguity_issues
# ---------------------------------------------------------------------------


class TestAmbiguityIssues:
    def test_no_ambiguity_when_definitions_match(self):
        first_definition = {"AI": "Artificial Intelligence"}
        item = _item(abbr="AI", inline_definition="Artificial Intelligence")
        assert _ambiguity_issues(item, first_definition) == []

    def test_ambiguity_when_definitions_differ(self):
        first_definition = {"RAF": "Royal Air Force"}
        item = _item(
            abbr="RAF", inline_definition="Red Army Faction", occurrence_number=2
        )
        issues = _ambiguity_issues(item, first_definition)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.MEDIUM
        assert "Ambiguous abbreviation" in issues[0].title

    def test_no_ambiguity_without_prior_definition(self):
        first_definition: dict[str, str] = {}
        item = _item(abbr="AI", inline_definition="Artificial Intelligence")
        assert _ambiguity_issues(item, first_definition) == []

    def test_no_ambiguity_when_no_inline_definition(self):
        first_definition = {"AI": "Artificial Intelligence"}
        item = _item(abbr="AI", inline_definition="")
        assert _ambiguity_issues(item, first_definition) == []


# ---------------------------------------------------------------------------
# build_issues (integration)
# ---------------------------------------------------------------------------


class TestBuildIssues:
    def test_empty_abbreviations_returns_empty(self):
        state = _state(abbreviations=[])
        assert build_issues(state) == []

    def test_no_section_found_creates_global_issue(self):
        state = _state(
            abbreviations=[
                _item(abbr="AI", inline_definition="Artificial Intelligence")
            ],
            abbreviations_section_found=False,
        )
        issues = build_issues(state)
        section_issues = [i for i in issues if "No Abbreviations section" in i.title]
        assert len(section_issues) == 1

    def test_ignored_item_only_produces_ignored_issue(self):
        state = _state(
            abbreviations=[_item(abbr="Mr.", ignored=True, ignored_reason="Title")],
            abbreviations_section_found=True,
        )
        issues = build_issues(state)
        assert len(issues) == 1
        assert issues[0].severity == SeverityEnum.NONE
        assert "ignored" in issues[0].title

    def test_all_ignored_no_section_skips_missing_section_issue(self):
        state = _state(
            abbreviations=[
                _item(abbr="Mr.", ignored=True, ignored_reason="Personal title"),
                _item(abbr="U.S.", ignored=True, ignored_reason="Exempt"),
            ],
            abbreviations_section_found=False,
        )
        issues = build_issues(state)
        section_issues = [i for i in issues if "No Abbreviations section" in i.title]
        assert len(section_issues) == 0

    def test_compliant_abbreviation_produces_none_severity_issues(self):
        state = _state(
            abbreviations=[
                _item(
                    abbr="AI",
                    inline_definition="Artificial Intelligence",
                    abbreviations_section_definition="Artificial Intelligence",
                    occurrence_number=1,
                ),
                _item(
                    abbr="AI",
                    abbreviations_section_definition="Artificial Intelligence",
                    occurrence_number=2,
                ),
            ],
            abbreviations_section_found=True,
        )
        issues = build_issues(state)
        medium_issues = [i for i in issues if i.severity == SeverityEnum.MEDIUM]
        assert len(medium_issues) == 0

    def test_missing_inline_and_section_produces_two_medium(self):
        state = _state(
            abbreviations=[
                _item(abbr="CO2", occurrence_number=1),
            ],
            abbreviations_section_found=True,
        )
        issues = build_issues(state)
        medium_issues = [i for i in issues if i.severity == SeverityEnum.MEDIUM]
        assert len(medium_issues) == 2
        titles = {i.title for i in medium_issues}
        assert "Abbreviation not defined at first use" in titles
        assert "Abbreviation missing from Abbreviations section" in titles

    def test_ambiguous_abbreviation_flagged(self):
        state = _state(
            abbreviations=[
                _item(
                    abbr="RAF", inline_definition="Royal Air Force", occurrence_number=1
                ),
                _item(
                    abbr="RAF",
                    inline_definition="Red Army Faction",
                    occurrence_number=2,
                ),
            ],
            abbreviations_section_found=False,
        )
        issues = build_issues(state)
        ambiguity = [i for i in issues if "Ambiguous" in i.title]
        assert len(ambiguity) == 1

    def test_line_range_propagated_to_issues(self):
        state = _state(
            abbreviations=[
                _item(
                    abbr="AI",
                    inline_definition="Artificial Intelligence",
                    occurrence_number=1,
                    line_start=5,
                    line_end=7,
                ),
            ],
            abbreviations_section_found=False,
        )
        issues = build_issues(state)
        located = [i for i in issues if i.start_line is not None]
        assert len(located) > 0
        assert all(i.start_line == 5 and i.end_line == 7 for i in located)
