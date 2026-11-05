"""The passage an issue carries, from the reported quote to the published field."""

import uuid
from datetime import UTC, datetime

from lib.models.issue import Issue
from lib.services.issue_persistence import _passage_columns
from lib.workflows.models import LocatedQuote, SeverityEnum, WorkflowRunType


def _issue(**columns) -> Issue:
    now = datetime.now(UTC)
    return Issue(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workflow_run_id=uuid.uuid4(),
        issue_hash="hash",
        title="Trigger word",
        description="Certainty language.",
        severity=SeverityEnum.MEDIUM,
        workflow_type=WorkflowRunType.ADVOCACY_TONE_V2,
        start_line=2,
        end_line=4,
        created_at=now,
        updated_at=now,
        **columns,
    )


def test_a_reported_passage_round_trips_to_the_published_shape():
    quote = LocatedQuote(
        original_text="**certainly** works",
        display_text="certainly works",
        display_occurrence=1,
        start_line=3,
        end_line=3,
    )

    issue = _issue(**_passage_columns(quote))

    assert issue.passage is not None
    assert issue.passage.model_dump() == {
        "original_text": "**certainly** works",
        "display_text": "certainly works",
        "display_occurrence": 1,
        "start_line": 3,
        "end_line": 3,
    }
    assert "passage" in issue.model_dump()


def test_control_characters_are_stripped_like_every_other_text_column():
    quote = LocatedQuote(
        original_text="a\x00b",
        display_text="a\x00b",
        display_occurrence=0,
        start_line=3,
        end_line=3,
    )

    columns = _passage_columns(quote)

    assert columns["passage_text"] == "ab"
    assert columns["passage_display_text"] == "ab"


def test_an_issue_without_a_passage_publishes_none():
    assert _passage_columns(None) == {
        "passage_text": None,
        "passage_display_text": None,
        "passage_display_occurrence": None,
        "passage_line": None,
    }
    assert _issue().passage is None
    # A half-written row is not a passage either.
    assert _issue(passage_text="x").passage is None
