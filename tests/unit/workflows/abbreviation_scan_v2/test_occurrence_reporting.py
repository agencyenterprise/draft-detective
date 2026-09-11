"""Tests for the abbreviation occurrence collector tool."""

from lib.workflows.abbreviation_scan_v2.occurrence_reporting import (
    MAX_PER_CALL,
    AbbreviationReporter,
)


def _entry(**overrides) -> dict:
    entry = {
        "abbr": "NATO",
        "inline_definition": "",
        "occurrence_number": 1,
        "line_start": 10,
        "line_end": 10,
        "abbreviations_section_definition": None,
        "ignored": False,
        "ignored_reason": None,
    }
    entry.update(overrides)
    return entry


def _record(reporter: AbbreviationReporter, *entries: dict) -> str:
    return reporter.tools[0].invoke({"occurrences": list(entries)})


class TestRecording:
    def test_records_a_batch(self):
        reporter = AbbreviationReporter()
        result = _record(
            reporter,
            _entry(),
            _entry(abbr="OSCE", line_start=11, line_end=11),
        )
        assert "Recorded 2" in result
        assert [o.abbr for o in reporter.occurrences] == ["NATO", "OSCE"]

    def test_accumulates_across_calls(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry())
        _record(reporter, _entry(occurrence_number=2, line_start=20, line_end=20))
        assert len(reporter.occurrences) == 2
        assert "2 total so far" in _record(
            reporter, _entry(occurrence_number=2, line_start=20, line_end=20)
        )

    def test_fields_round_trip(self):
        reporter = AbbreviationReporter()
        _record(
            reporter,
            _entry(
                inline_definition="North Atlantic Treaty Organization",
                abbreviations_section_definition="North Atlantic Treaty Organization",
                ignored=True,
                ignored_reason="heading",
            ),
        )
        item = reporter.occurrences[0]
        assert item.inline_definition == "North Atlantic Treaty Organization"
        assert item.abbreviations_section_definition == "North Atlantic Treaty Organization"
        assert item.ignored is True
        assert item.ignored_reason == "heading"

    def test_snapshot_cannot_mutate_collector(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry())
        reporter.occurrences.clear()
        assert len(reporter.occurrences) == 1


class TestDeduplication:
    def test_identical_occurrence_recorded_once(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry())
        result = _record(reporter, _entry())
        assert "duplicate" in result.lower()
        assert len(reporter.occurrences) == 1

    def test_same_abbr_on_a_different_line_is_kept(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry())
        _record(reporter, _entry(occurrence_number=2, line_start=50, line_end=50))
        assert len(reporter.occurrences) == 2


class TestValidation:
    def test_blank_abbr_rejected(self):
        reporter = AbbreviationReporter()
        result = _record(reporter, _entry(abbr="  "))
        assert "Not recorded" in result
        assert reporter.occurrences == []

    def test_bad_line_range_rejected(self):
        reporter = AbbreviationReporter()
        result = _record(reporter, _entry(line_start=10, line_end=5))
        assert "line_end" in result
        assert reporter.occurrences == []

    def test_zero_occurrence_number_rejected(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(occurrence_number=0))
        assert reporter.occurrences == []

    def test_ignored_requires_a_reason(self):
        reporter = AbbreviationReporter()
        result = _record(reporter, _entry(ignored=True, ignored_reason=None))
        assert "ignored_reason" in result
        assert reporter.occurrences == []

    def test_valid_entries_survive_an_invalid_sibling(self):
        reporter = AbbreviationReporter()
        result = _record(
            reporter,
            _entry(),
            _entry(abbr="", line_start=11, line_end=11),
            _entry(abbr="OSCE", line_start=12, line_end=12),
        )
        assert [o.abbr for o in reporter.occurrences] == ["NATO", "OSCE"]
        assert "Recorded 2" in result and "Not recorded" in result


class TestBatchLimits:
    def test_empty_batch_is_reported(self):
        reporter = AbbreviationReporter()
        assert "empty" in _record(reporter).lower()

    def test_oversized_batch_is_refused_whole(self):
        reporter = AbbreviationReporter()
        entries = [
            _entry(occurrence_number=i + 1, line_start=i + 1, line_end=i + 1)
            for i in range(MAX_PER_CALL + 1)
        ]
        result = _record(reporter, *entries)
        assert "exceeds" in result
        assert reporter.occurrences == []

    def test_batch_at_the_limit_is_accepted(self):
        reporter = AbbreviationReporter()
        entries = [
            _entry(occurrence_number=i + 1, line_start=i + 1, line_end=i + 1)
            for i in range(MAX_PER_CALL)
        ]
        _record(reporter, *entries)
        assert len(reporter.occurrences) == MAX_PER_CALL


class TestIsolation:
    def test_collectors_do_not_share_state(self):
        first, second = AbbreviationReporter(), AbbreviationReporter()
        _record(first, _entry())
        assert second.occurrences == []


class TestNormalisation:
    """Blank strings must not masquerade as definitions.

    `build_issues` tells "no definition" from "a definition" by `None` and by
    truthiness, so an unnormalised `" "` or `""` from the model silently turns a
    rule off — and an empty section definition also invents a Rule 4 mismatch
    against nothing.
    """

    def test_whitespace_inline_definition_becomes_empty(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(inline_definition="   "))
        assert reporter.occurrences[0].inline_definition == ""

    def test_inline_definition_is_trimmed(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(inline_definition="  North Atlantic Treaty Organization  "))
        assert reporter.occurrences[0].inline_definition == "North Atlantic Treaty Organization"

    def test_empty_section_definition_becomes_none(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(abbreviations_section_definition=""))
        assert reporter.occurrences[0].abbreviations_section_definition is None

    def test_whitespace_section_definition_becomes_none(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(abbreviations_section_definition="  "))
        assert reporter.occurrences[0].abbreviations_section_definition is None

    def test_real_section_definition_survives_trimmed(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(abbreviations_section_definition=" Artificial Intelligence "))
        assert reporter.occurrences[0].abbreviations_section_definition == "Artificial Intelligence"

    def test_blank_ignored_reason_becomes_none(self):
        reporter = AbbreviationReporter()
        _record(reporter, _entry(ignored=True, ignored_reason="heading  "))
        assert reporter.occurrences[0].ignored_reason == "heading"


class TestNormalisationKeepsRulesFiring:
    """The end-to-end consequence: the rules still see the violations."""

    def test_blank_definitions_still_produce_both_findings(self):
        from lib.workflows.abbreviation_scan_v2.issues import build_issues
        from lib.workflows.abbreviation_scan_v2.state import (
            AbbreviationScanV2Config,
            AbbreviationScanV2State,
        )

        reporter = AbbreviationReporter()
        _record(
            reporter,
            _entry(inline_definition=" ", abbreviations_section_definition=""),
        )
        state = AbbreviationScanV2State(
            config=AbbreviationScanV2Config(project_id="test-project"),
            abbreviations=reporter.occurrences,
            abbreviations_section_found=True,
        )
        titles = [i.title for i in build_issues(state)]
        assert "Abbreviation not defined at first use" in titles
        assert "Abbreviation missing from Abbreviations section" in titles
        assert "Inline definition does not match Abbreviations section" not in titles
