"""Document processing's initial state takes the revision's own main file,
and the shared supporting files."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.file import File, FileRole
from lib.services.files.document import FileDocument
from lib.workflows.document_processing.manifest import DocumentProcessingManifest
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.models import WorkflowRunType
from tests.unit.services.files.fake_file_query import file_row, patched_file_query

MODULE = "lib.workflows.document_processing.manifest"
PROJECT_ID = uuid.uuid4()


async def _as_document(file: File) -> FileDocument:
    return FileDocument(
        file_id=str(file.id),
        file_name=file.file_name,
        file_path=file.file_path,
        file_type=file.file_type,
        markdown="",
        markdown_token_count=0,
    )


async def _initial_state(rows: list[File], revision: int) -> DocumentProcessingState:
    config = DocumentProcessingWorkflowConfig(
        type=WorkflowRunType.DOCUMENT_PROCESSING, project_id=str(PROJECT_ID)
    )
    with (
        patched_file_query(rows, MODULE),
        patch(f"{MODULE}.load_file_document", AsyncMock(side_effect=_as_document)),
    ):
        return await DocumentProcessingManifest().create_initial_state(
            config, existing_states=[], revision=revision
        )


@pytest.mark.asyncio
async def test_takes_the_revision_main_file_and_shared_supporting_files() -> None:
    main_1 = file_row(PROJECT_ID, FileRole.MAIN, 1)
    main_2 = file_row(PROJECT_ID, FileRole.MAIN, 2)
    support = file_row(PROJECT_ID, FileRole.SUPPORT, None)
    state = await _initial_state([main_1, support, main_2], revision=2)
    assert state.file.file_id == str(main_2.id)
    assert state.supporting_files is not None
    assert [f.file_id for f in state.supporting_files] == [str(support.id)]


@pytest.mark.asyncio
async def test_a_shared_main_row_is_not_the_revision_main_file() -> None:
    stray = file_row(PROJECT_ID, FileRole.MAIN, None)
    main_2 = file_row(PROJECT_ID, FileRole.MAIN, 2)
    state = await _initial_state([stray, main_2], revision=2)
    assert state.file.file_id == str(main_2.id)


@pytest.mark.asyncio
async def test_fails_when_the_revision_has_no_main_file() -> None:
    with pytest.raises(AssertionError):
        await _initial_state([file_row(PROJECT_ID, FileRole.MAIN, 1)], revision=2)
