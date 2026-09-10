"""Unit tests for DocumentSummarizationManifest.create_initial_state seeding.

document_summarization is an accumulating workflow: it carries per-file
summaries across runs so subsequent runs only summarize new files. Since runs
no longer share a langgraph_thread_id, the prior run's summaries are handed in
via prior_self_state instead of the checkpointer — these tests pin that seeding.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.workflows.document_summarization.manifest import (
    DocumentSummarizationManifest,
)
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    DocumentSummarizationWorkflowConfig,
    FileSummary,
)
from lib.workflows.models import WorkflowRunType


def _config() -> DocumentSummarizationWorkflowConfig:
    return DocumentSummarizationWorkflowConfig(
        type=WorkflowRunType.DOCUMENT_SUMMARIZATION,
        project_id=str(uuid.uuid4()),
    )


def _file_summary(file_id: str) -> FileSummary:
    return FileSummary(
        file_id=file_id,
        title="t",
        authors="",
        publication_date="Unknown",
        abstract="Unknown",
        summary="s",
    )


def _prior_state(file_id: str) -> DocumentSummarizationState:
    return DocumentSummarizationState(
        type=WorkflowRunType.DOCUMENT_SUMMARIZATION,
        config=_config(),
        main_file_id="main",
        supporting_file_ids=[],
        summaries=[_file_summary(file_id)],
    )


@pytest.mark.asyncio
async def test_create_initial_state_seeds_summaries_from_prior():
    """The new run carries forward the prior run's summaries."""
    with (
        patch(
            "lib.workflows.document_summarization.manifest.get_main_file_id",
            new=AsyncMock(return_value="main"),
        ),
        patch(
            "lib.workflows.document_summarization.manifest.get_processed_supporting_file_ids",
            new=AsyncMock(return_value=[]),
        ),
    ):
        state = await DocumentSummarizationManifest().create_initial_state(
            _config(), [], 1, prior_self_state=_prior_state("f1")
        )

    assert [s.file_id for s in state.summaries] == ["f1"]


@pytest.mark.asyncio
async def test_create_initial_state_empty_without_prior():
    """A first run (no prior state) starts with no summaries."""
    with (
        patch(
            "lib.workflows.document_summarization.manifest.get_main_file_id",
            new=AsyncMock(return_value="main"),
        ),
        patch(
            "lib.workflows.document_summarization.manifest.get_processed_supporting_file_ids",
            new=AsyncMock(return_value=[]),
        ),
    ):
        state = await DocumentSummarizationManifest().create_initial_state(
            _config(), [], 1
        )

    assert state.summaries == []
