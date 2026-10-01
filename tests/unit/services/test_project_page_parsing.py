"""The project page's reads pull state fields straight out of `state_json`.

Those fields are whatever was persisted, by whichever version of a workflow
wrote them, so the parsers must keep what still validates and skip the rest
rather than fail the whole page. These pin that behaviour without a database.
"""

import uuid

from langchain_core.messages import HumanMessage

from lib.services.project_content import _text_or_none, _validate_items
from lib.services.project_overview import current_run_errors
from lib.services.workflow_runs import _without_messages
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowErrorSeverity, WorkflowRunType
from lib.workflows.reference_downloader.state import ReferenceFetchResult
from lib.workflows.reference_extraction.state import ExtractedReference
from lib.workflows.simple_deep_agent.state import (
    SimpleDeepAgentConfig,
    SimpleDeepAgentState,
)

RUN_ID = uuid.uuid4()


def _error(run_id: object, **extra: object) -> dict[str, object]:
    return {"task_name": "t", "error": "e", "workflow_run_id": str(run_id), **extra}


class TestCurrentRunErrors:
    def test_keeps_only_this_runs_errors(self):
        errors = current_run_errors(RUN_ID, [_error(RUN_ID), _error(uuid.uuid4())])

        assert [e.workflow_run_id for e in errors] == [str(RUN_ID)]

    def test_drops_errors_without_a_run_id(self):
        """Errors from before runs were stamped cannot be attributed, so none are shown."""
        assert current_run_errors(RUN_ID, [{"task_name": "t", "error": "e"}]) == []

    def test_errors_without_a_severity_count_as_blocking(self):
        [error] = current_run_errors(RUN_ID, [_error(RUN_ID)])

        assert error.severity == WorkflowErrorSeverity.ERROR

    def test_skips_entries_that_no_longer_validate(self):
        errors = current_run_errors(
            RUN_ID, [{"workflow_run_id": str(RUN_ID)}, "junk", _error(RUN_ID)]
        )

        assert len(errors) == 1

    def test_anything_but_a_list_is_no_errors(self):
        assert current_run_errors(RUN_ID, None) == []
        assert current_run_errors(RUN_ID, {"errors": []}) == []


class TestValidateItems:
    def test_keeps_valid_items_and_skips_the_rest(self):
        items = _validate_items(
            ExtractedReference,
            [{"id": "r1", "text": "Smith"}, {"id": "r2"}, "junk", None],
        )

        assert [item.id for item in items] == ["r1"]

    def test_drops_the_named_keys_before_validating(self):
        [result] = _validate_items(
            ReferenceFetchResult,
            [
                {
                    "reference_id": "r1",
                    "input_reference": "Smith",
                    "status": "completed",
                    "messages": [{"type": "human", "content": "find it"}],
                }
            ],
            drop=("messages",),
        )

        assert result.messages == []

    def test_anything_but_a_list_is_empty(self):
        assert _validate_items(ExtractedReference, None) == []
        assert _validate_items(ExtractedReference, {"id": "r1"}) == []


class TestWithoutMessages:
    def test_empties_the_transcript_and_leaves_the_rest(self):
        state = SimpleDeepAgentState(
            type=WorkflowRunType.RECOMMENDATION_CHECK,
            config=SimpleDeepAgentConfig(
                type=WorkflowRunType.RECOMMENDATION_CHECK, project_id="p"
            ),
            messages=[HumanMessage(content="hi")],
        )

        stripped = _without_messages(state)

        assert isinstance(stripped, SimpleDeepAgentState)
        assert stripped.messages == []
        assert stripped.config == state.config
        assert len(state.messages) == 1  # the original is not modified

    def test_states_without_a_transcript_pass_through(self):
        state = DocumentProcessingState.model_construct()

        assert _without_messages(state) is state

    def test_no_state_stays_no_state(self):
        assert _without_messages(None) is None


class TestTextOrNone:
    def test_keeps_text(self):
        assert _text_or_none("The Draft") == "The Draft"

    def test_anything_else_is_none(self):
        """An older summary shape must not turn the whole document read into a 500."""
        assert _text_or_none(["A. Author"]) is None
        assert _text_or_none({"name": "A"}) is None
        assert _text_or_none(None) is None
