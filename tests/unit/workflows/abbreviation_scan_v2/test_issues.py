"""Tests for abbreviation scan v2 issue conversion.

Exercised through `build_issues` rather than its helpers: the rules are the
contract, and each of them now reports at most once per abbreviation.
"""

from typing import List, Optional

from lib.workflows.abbreviation_scan_v2.issues import build_issues
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


def _titles(issues) -> List[str]:
    return [i.title for i in issues]


def _occurrences(abbr: str, count: int, **overrides) -> List[AbbreviationItem]:
    """One abbreviation repeated `count` times on ascending lines."""
    return [
        _item(abbr=abbr, occurrence_number=n, line_start=n * 10, line_end=n * 10, **overrides)
        for n in range(1, count + 1)
    ]


class TestNoneSeverityIsNeverReported:
    def test_passing_abbreviation_produces_nothing(self):
        issues = build_issues(
            _state(
                [_item(inline_definition="Artificial Intelligence",
                       abbreviations_section_definition="Artificial Intelligence")],
                abbreviations_section_found=True,
            )
        )
        assert issues == []

    def test_ignored_occurrences_produce_nothing(self):
        issues = build_issues(
            _state([_item(ignored=True, ignored_reason="heading")],
                   abbreviations_section_found=True)
        )
        assert issues == []

    def test_subsequent_occurrences_produce_nothing(self):
        items = [
            _item(inline_definition="Artificial Intelligence",
                  abbreviations_section_definition="Artificial Intelligence"),
            *_occurrences("AI", 5, abbreviations_section_definition="Artificial Intelligence")[1:],
        ]
        assert build_issues(_state(items, abbreviations_section_found=True)) == []

    def test_every_reported_issue_is_medium(self):
        items = _occurrences("AI", 4) + _occurrences("ML", 3)
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert issues
        assert all(i.severity == SeverityEnum.MEDIUM for i in issues)


class TestRule1MissingSection:
    def test_reported_once_when_section_absent(self):
        issues = build_issues(_state(_occurrences("AI", 3) + _occurrences("ML", 3)))
        assert _titles(issues).count("No Abbreviations section found") == 1

    def test_not_reported_when_section_present(self):
        issues = build_issues(_state(_occurrences("AI", 3), abbreviations_section_found=True))
        assert "No Abbreviations section found" not in _titles(issues)

    def test_not_reported_when_every_occurrence_is_ignored(self):
        items = [_item(ignored=True, ignored_reason="exempt class")]
        assert build_issues(_state(items)) == []


class TestRule2NotDefinedAtFirstUse:
    def test_reported_once_per_abbreviation(self):
        issues = build_issues(
            _state(_occurrences("AI", 40), abbreviations_section_found=True)
        )
        assert _titles(issues).count("Abbreviation not defined at first use") == 1

    def test_anchored_to_the_first_occurrence(self):
        issues = build_issues(
            _state(_occurrences("AI", 5), abbreviations_section_found=True)
        )
        issue = next(i for i in issues if i.title == "Abbreviation not defined at first use")
        assert issue.start_line == 10

    def test_first_occurrence_found_regardless_of_list_order(self):
        items = list(reversed(_occurrences("AI", 5)))
        issues = build_issues(_state(items, abbreviations_section_found=True))
        issue = next(i for i in issues if i.title == "Abbreviation not defined at first use")
        assert issue.start_line == 10

    def test_not_reported_when_defined(self):
        items = _occurrences("AI", 3, abbreviations_section_definition="Artificial Intelligence")
        items[0] = _item(inline_definition="Artificial Intelligence", line_start=10, line_end=10,
                         abbreviations_section_definition="Artificial Intelligence")
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert "Abbreviation not defined at first use" not in _titles(issues)

    def test_ignored_first_occurrence_does_not_count_as_first_use(self):
        items = [
            _item(occurrence_number=1, line_start=5, line_end=5, ignored=True,
                  ignored_reason="heading", inline_definition="Artificial Intelligence"),
            _item(occurrence_number=2, line_start=30, line_end=30),
        ]
        issues = build_issues(_state(items, abbreviations_section_found=True))
        issue = next(i for i in issues if i.title == "Abbreviation not defined at first use")
        assert issue.start_line == 30


class TestRule3MissingFromSection:
    def test_reported_once_per_abbreviation_not_per_occurrence(self):
        issues = build_issues(
            _state(_occurrences("AI", 40), abbreviations_section_found=True)
        )
        assert _titles(issues).count("Abbreviation missing from Abbreviations section") == 1

    def test_one_issue_for_each_distinct_abbreviation(self):
        items = _occurrences("AI", 20) + _occurrences("ML", 15) + _occurrences("NLP", 10)
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert _titles(issues).count("Abbreviation missing from Abbreviations section") == 3

    def test_not_reported_when_listed(self):
        items = _occurrences("AI", 5, abbreviations_section_definition="Artificial Intelligence")
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert "Abbreviation missing from Abbreviations section" not in _titles(issues)

    def test_not_reported_when_no_section_exists(self):
        issues = build_issues(_state(_occurrences("AI", 5)))
        assert "Abbreviation missing from Abbreviations section" not in _titles(issues)


class TestRule4DefinitionMismatch:
    def test_reported_when_inline_differs_from_section(self):
        items = [
            _item(inline_definition="Artificial Insemination",
                  abbreviations_section_definition="Artificial Intelligence")
        ]
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert "Inline definition does not match Abbreviations section" in _titles(issues)

    def test_not_reported_for_trivial_differences(self):
        items = [
            _item(inline_definition="artificial intelligence.",
                  abbreviations_section_definition="Artificial Intelligence")
        ]
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert "Inline definition does not match Abbreviations section" not in _titles(issues)

    def test_reported_once_per_abbreviation(self):
        items = _occurrences("AI", 10, inline_definition="Artificial Insemination",
                             abbreviations_section_definition="Artificial Intelligence")
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert _titles(issues).count("Inline definition does not match Abbreviations section") == 1


class TestRule5Ambiguous:
    def test_reported_when_a_later_definition_conflicts(self):
        items = [
            _item(inline_definition="Artificial Intelligence", occurrence_number=1,
                  line_start=10, line_end=10,
                  abbreviations_section_definition="Artificial Intelligence"),
            _item(inline_definition="Analogue Input", occurrence_number=2,
                  line_start=80, line_end=80,
                  abbreviations_section_definition="Artificial Intelligence"),
        ]
        issues = build_issues(_state(items, abbreviations_section_found=True))
        ambiguous = [i for i in issues if i.title == "Ambiguous abbreviation"]
        assert len(ambiguous) == 1
        assert ambiguous[0].start_line == 80

    def test_reported_once_even_with_several_conflicts(self):
        items = [
            _item(inline_definition="Artificial Intelligence", occurrence_number=1,
                  line_start=10, line_end=10,
                  abbreviations_section_definition="Artificial Intelligence"),
            *[
                _item(inline_definition="Analogue Input", occurrence_number=n,
                      line_start=n * 10, line_end=n * 10,
                      abbreviations_section_definition="Artificial Intelligence")
                for n in range(2, 8)
            ],
        ]
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert _titles(issues).count("Ambiguous abbreviation") == 1

    def test_not_reported_for_consistent_repeats(self):
        items = _occurrences("AI", 5, inline_definition="Artificial Intelligence",
                             abbreviations_section_definition="Artificial Intelligence")
        issues = build_issues(_state(items, abbreviations_section_found=True))
        assert "Ambiguous abbreviation" not in _titles(issues)


class TestVolume:
    def test_many_occurrences_stay_proportional_to_distinct_abbreviations(self):
        """A long document must not produce one issue per occurrence."""
        items: List[AbbreviationItem] = []
        for index in range(30):
            items.extend(_occurrences(f"AB{index}", 30))
        issues = build_issues(_state(items, abbreviations_section_found=True))
        # 30 abbreviations x (Rule 2 + Rule 3), not 30 x 30 occurrences.
        assert len(issues) == 60
        assert len(items) == 900


class TestEmptyState:
    def test_no_abbreviations_yields_nothing(self):
        assert build_issues(_state()) == []
