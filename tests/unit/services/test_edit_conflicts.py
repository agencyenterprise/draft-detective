"""Tests for reducing overlapping proposed edits to one winner per passage."""

import random
import uuid
from datetime import UTC, datetime, timedelta

from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.services.edit_conflicts import (
    EditCandidate,
    EditDecision,
    resolve_edit_conflicts,
)
from lib.workflows.models import SeverityEnum

_LINES = [
    "The Energy Supply chapter reports a 14% rise in output for 2019.",
    "Figure 3 and **Figure 3** close the section.",
]
_EARLIER = datetime(2026, 1, 1, tzinfo=UTC)


def _candidate(
    original_text: str,
    replacement_text: str = "replacement",
    *,
    start_line: int = 1,
    status: IssueEditStatus = IssueEditStatus.PROPOSED,
    severity: SeverityEnum = SeverityEnum.MEDIUM,
    created_at: datetime = _EARLIER,
    edit_id: uuid.UUID | None = None,
    workflow_type: str = "reference_validation_v2",
) -> EditCandidate:
    edit = IssueEdit(
        id=edit_id or uuid.uuid4(),
        issue_id=uuid.uuid4(),
        position=0,
        original_text=original_text,
        replacement_text=replacement_text,
        start_line=start_line,
        end_line=start_line,
        rationale="because",
        status=status,
    )
    return EditCandidate(
        edit=edit,
        issue_severity=severity,
        issue_created_at=created_at,
        workflow_type=workflow_type,
    )


def _by_id(decisions: list[EditDecision]) -> dict[uuid.UUID, EditDecision]:
    return {decision.edit_id: decision for decision in decisions}


class TestLocating:
    def test_a_quote_found_once_is_applied_with_its_span(self):
        candidate = _candidate("14% rise")

        (decision,) = resolve_edit_conflicts([candidate], _LINES)

        assert decision.outcome == "apply"
        assert decision.span is not None
        assert _LINES[0][decision.span[0] : decision.span[1]] == "14% rise"
        assert decision.conflicts_with == []
        assert decision.winner_id is None

    def test_a_quote_is_matched_through_whitespace_drift(self):
        (decision,) = resolve_edit_conflicts([_candidate("Energy Supply")], _LINES)

        assert decision.outcome == "apply"
        assert decision.span is not None
        assert _LINES[0][decision.span[0] : decision.span[1]] == "Energy Supply"

    def test_a_quote_the_line_does_not_carry_is_unlocatable(self):
        (decision,) = resolve_edit_conflicts([_candidate("a 40% drop")], _LINES)

        assert decision.outcome == "unlocatable"
        assert decision.span is None

    def test_a_quote_the_line_carries_twice_is_unlocatable(self):
        (decision,) = resolve_edit_conflicts(
            [_candidate("Figure 3", start_line=2)], _LINES
        )

        assert decision.outcome == "unlocatable"

    def test_a_line_number_outside_the_document_is_unlocatable(self):
        (decision,) = resolve_edit_conflicts(
            [_candidate("14% rise", start_line=99)], _LINES
        )

        assert decision.outcome == "unlocatable"

    def test_a_rejected_edit_is_reported_and_never_competes(self):
        rejected = _candidate("14% rise", status=IssueEditStatus.REJECTED)
        overlapping = _candidate("a 14% rise in output")

        decisions = _by_id(resolve_edit_conflicts([rejected, overlapping], _LINES))

        assert decisions[rejected.edit.id].outcome == "rejected"
        assert decisions[rejected.edit.id].span is None
        assert decisions[overlapping.edit.id].outcome == "apply"


class TestConflicts:
    def test_edits_that_do_not_overlap_all_apply(self):
        first = _candidate("Energy Supply")
        second = _candidate("14% rise")
        third = _candidate("**Figure 3**", start_line=2)

        decisions = resolve_edit_conflicts([first, second, third], _LINES)

        assert [decision.outcome for decision in decisions] == ["apply"] * 3

    def test_edits_on_different_lines_never_conflict(self):
        # The same quote text on two lines: spans overlap numerically, lines do not.
        lines = ["shared quote here", "shared quote here"]
        first = _candidate("shared quote", start_line=1)
        second = _candidate("shared quote", start_line=2)

        decisions = resolve_edit_conflicts([first, second], lines)

        assert [decision.outcome for decision in decisions] == ["apply", "apply"]

    def test_an_accepted_edit_beats_a_proposed_one(self):
        accepted = _candidate("14% rise", status=IssueEditStatus.ACCEPTED)
        proposed = _candidate(
            "a 14% rise in output", severity=SeverityEnum.HIGH, created_at=_EARLIER
        )

        decisions = _by_id(resolve_edit_conflicts([proposed, accepted], _LINES))

        assert decisions[accepted.edit.id].outcome == "apply"
        assert decisions[proposed.edit.id].outcome == "conflict"
        assert decisions[proposed.edit.id].winner_id == accepted.edit.id
        assert decisions[proposed.edit.id].conflicts_with == [accepted.edit.id]
        assert decisions[accepted.edit.id].conflicts_with == [proposed.edit.id]

    def test_severity_breaks_a_tie_before_age(self):
        high = _candidate(
            "14% rise",
            severity=SeverityEnum.HIGH,
            created_at=_EARLIER + timedelta(days=7),
        )
        low = _candidate("a 14% rise", severity=SeverityEnum.LOW)

        decisions = _by_id(resolve_edit_conflicts([low, high], _LINES))

        assert decisions[high.edit.id].outcome == "apply"
        assert decisions[low.edit.id].outcome == "conflict"

    def test_the_older_issue_wins_at_equal_severity(self):
        older = _candidate("14% rise", created_at=_EARLIER)
        newer = _candidate("a 14% rise", created_at=_EARLIER + timedelta(hours=1))

        decisions = _by_id(resolve_edit_conflicts([newer, older], _LINES))

        assert decisions[older.edit.id].outcome == "apply"
        assert decisions[newer.edit.id].outcome == "conflict"

    def test_the_lower_id_wins_when_everything_else_ties(self):
        low_id = _candidate("14% rise", edit_id=uuid.UUID(int=1))
        high_id = _candidate("a 14% rise", edit_id=uuid.UUID(int=2))

        decisions = _by_id(resolve_edit_conflicts([high_id, low_id], _LINES))

        assert decisions[low_id.edit.id].outcome == "apply"
        assert decisions[high_id.edit.id].outcome == "conflict"

    def test_a_naive_timestamp_is_compared_as_utc(self):
        older = _candidate("14% rise", created_at=datetime(2026, 1, 1))
        newer = _candidate("a 14% rise", created_at=_EARLIER + timedelta(hours=1))

        decisions = _by_id(resolve_edit_conflicts([newer, older], _LINES))

        assert decisions[older.edit.id].outcome == "apply"

    def test_a_chain_of_overlaps_is_one_group(self):
        # "reports a" — "a 14% rise" — "rise in output": the ends overlap in a
        # chain, so all three compete even though the outer two do not touch.
        first = _candidate("reports a", severity=SeverityEnum.LOW)
        middle = _candidate("a 14% rise", severity=SeverityEnum.HIGH)
        last = _candidate("rise in output", severity=SeverityEnum.LOW)

        decisions = _by_id(resolve_edit_conflicts([first, middle, last], _LINES))

        assert decisions[middle.edit.id].outcome == "apply"
        assert decisions[first.edit.id].outcome == "conflict"
        assert decisions[last.edit.id].outcome == "conflict"
        assert decisions[first.edit.id].winner_id == middle.edit.id
        assert sorted(decisions[first.edit.id].conflicts_with, key=str) == sorted(
            [middle.edit.id, last.edit.id], key=str
        )

    def test_two_separate_groups_on_one_line_each_keep_a_winner(self):
        first_group = [
            _candidate("Energy Supply", severity=SeverityEnum.HIGH),
            _candidate("Energy Supply chapter", severity=SeverityEnum.LOW),
        ]
        second_group = [
            _candidate("14% rise", severity=SeverityEnum.HIGH),
            _candidate("a 14% rise", severity=SeverityEnum.LOW),
        ]

        decisions = _by_id(resolve_edit_conflicts(first_group + second_group, _LINES))

        applied = [d for d in decisions.values() if d.outcome == "apply"]
        assert {d.edit_id for d in applied} == {
            first_group[0].edit.id,
            second_group[0].edit.id,
        }

    def test_a_duplicate_proposal_keeps_one_and_reports_the_other(self):
        first = _candidate("14% rise", "15% rise", edit_id=uuid.UUID(int=1))
        duplicate = _candidate("14% rise", "15% rise", edit_id=uuid.UUID(int=2))

        decisions = _by_id(resolve_edit_conflicts([first, duplicate], _LINES))

        assert decisions[first.edit.id].outcome == "apply"
        assert decisions[duplicate.edit.id].outcome == "conflict"
        assert decisions[duplicate.edit.id].winner_id == first.edit.id


class TestDeterminism:
    def test_the_same_edits_resolve_the_same_way_in_any_order(self):
        candidates = [
            _candidate("Energy Supply", edit_id=uuid.UUID(int=10)),
            _candidate("Energy Supply chapter", edit_id=uuid.UUID(int=11)),
            _candidate("14% rise", edit_id=uuid.UUID(int=12)),
            _candidate("a 14% rise", edit_id=uuid.UUID(int=13)),
            _candidate("a 40% drop", edit_id=uuid.UUID(int=14)),
            _candidate("**Figure 3**", start_line=2, edit_id=uuid.UUID(int=15)),
            _candidate(
                "14% rise",
                status=IssueEditStatus.REJECTED,
                edit_id=uuid.UUID(int=16),
            ),
        ]
        expected = resolve_edit_conflicts(candidates, _LINES)

        shuffler = random.Random(7)
        for _ in range(10):
            shuffled = list(candidates)
            shuffler.shuffle(shuffled)
            assert resolve_edit_conflicts(shuffled, _LINES) == expected

    def test_decisions_come_back_in_line_then_span_order(self):
        decisions = resolve_edit_conflicts(
            [
                _candidate("**Figure 3**", start_line=2),
                _candidate("14% rise"),
                _candidate("Energy Supply"),
            ],
            _LINES,
        )

        assert [decision.line for decision in decisions] == [1, 1, 2]
        assert decisions[0].span is not None and decisions[1].span is not None
        assert decisions[0].span[0] < decisions[1].span[0]
