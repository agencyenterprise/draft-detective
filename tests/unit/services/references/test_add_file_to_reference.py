"""Unit tests for add_file_to_reference service function."""

import uuid
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.references.service import add_file_to_reference
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.reference_file_matching.state import (
    MatchSource,
    ReferenceFileMatch,
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)

PROJECT_ID = str(uuid.uuid4())


def _matching_state(matches: list[ReferenceFileMatch]) -> ReferenceFileMatchingState:
    return ReferenceFileMatchingState(
        type=WorkflowRunType.REFERENCE_FILE_MATCHING,
        config=ReferenceFileMatchingConfig(project_id=PROJECT_ID),
        file_id=str(uuid.uuid4()),
        matches=matches,
    )


def _extraction_state(reference_ids: list[str]) -> ReferenceExtractionState:
    return ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id=PROJECT_ID),
        file_id=str(uuid.uuid4()),
        extracted_references=[
            ExtractedReference(id=ref_id, text=f"Reference {ref_id}")
            for ref_id in reference_ids
        ],
    )


def _make_run() -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    return run


@pytest.fixture
def persist() -> Iterator[AsyncMock]:
    with patch(
        "lib.services.references.service.persist_workflow_run_state", new=AsyncMock()
    ) as m:
        yield m


def _patch_states(
    matching: tuple[MagicMock | None, ReferenceFileMatchingState | None],
    extraction: ReferenceExtractionState | None,
):
    return (
        patch(
            "lib.services.references.service._get_file_matching_workflow_state",
            new=AsyncMock(return_value=matching),
        ),
        patch(
            "lib.services.references.service.get_project_workflow_run_with_state",
            new=AsyncMock(return_value=(_make_run(), extraction)),
        ),
    )


async def _link(reference_id: str, file_id: str = "f_new") -> bool:
    return await add_file_to_reference(
        PROJECT_ID, file_id, reference_id, MatchSource.MANUAL_UPLOAD, revision=1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "matching, extraction",
    [
        pytest.param((None, None), _extraction_state(["r1"]), id="no-matching-run"),
        pytest.param(
            (_make_run(), None), _extraction_state(["r1"]), id="no-matching-state"
        ),
        pytest.param(
            (_make_run(), _matching_state([])), None, id="no-extraction-state"
        ),
        pytest.param(
            (_make_run(), _matching_state([])),
            _extraction_state(["r2"]),
            id="unknown-reference-id",
        ),
    ],
)
async def test_returns_false_without_writing(persist, matching, extraction):
    matching_patch, extraction_patch = _patch_states(matching, extraction)
    with matching_patch, extraction_patch:
        assert await _link("r1") is False

    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_links_file_and_replaces_previous_match_for_reference(persist):
    old = ReferenceFileMatch(
        reference_id="r1", file_id="f_old", source=MatchSource.AUTO_MATCHED
    )
    other = ReferenceFileMatch(
        reference_id="r2", file_id="f_other", source=MatchSource.AUTO_FETCHED
    )
    run = _make_run()
    matching_patch, extraction_patch = _patch_states(
        (run, _matching_state([old, other])), _extraction_state(["r1", "r2"])
    )

    with matching_patch, extraction_patch:
        assert await _link("r1") is True

    run_id, persisted = persist.await_args.args
    assert run_id == str(run.id)
    assert persisted.matches == [
        other,
        ReferenceFileMatch(
            reference_id="r1", file_id="f_new", source=MatchSource.MANUAL_UPLOAD
        ),
    ]
