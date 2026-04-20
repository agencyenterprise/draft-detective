"""Unit tests for delete_project_file_with_cleanup service function."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.services.projects import delete_project_file_with_cleanup


@pytest.mark.asyncio
async def test_happy_path_runs_all_three_steps_and_returns_tuple():
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    revision = 3

    delete_mock = AsyncMock(return_value=1)
    unlink_mock = AsyncMock(return_value=[ref_id])
    clear_fetch_mock = AsyncMock(return_value=1)

    with (
        patch("lib.services.projects.delete_project_files", delete_mock),
        patch("lib.services.projects.remove_file_from_references", unlink_mock),
        patch("lib.services.projects.remove_fetch_result_for_file", clear_fetch_mock),
    ):
        deleted_count, removed_reference_ids = await delete_project_file_with_cleanup(
            project_id, file_id, revision=revision
        )

    assert deleted_count == 1
    assert removed_reference_ids == [ref_id]
    delete_mock.assert_awaited_once_with(project_id, target_file_ids=[file_id])
    unlink_mock.assert_awaited_once_with(project_id, file_id, revision=revision)
    clear_fetch_mock.assert_awaited_once_with(project_id, file_id, revision=revision)


@pytest.mark.asyncio
async def test_file_not_found_short_circuits_cleanup_steps():
    """If the file wasn't actually deleted, we must not run reference cleanup —
    otherwise we'd unlink references / clear fetch results that still validly point at a file."""
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())

    delete_mock = AsyncMock(return_value=0)
    unlink_mock = AsyncMock()
    clear_fetch_mock = AsyncMock()

    with (
        patch("lib.services.projects.delete_project_files", delete_mock),
        patch("lib.services.projects.remove_file_from_references", unlink_mock),
        patch("lib.services.projects.remove_fetch_result_for_file", clear_fetch_mock),
    ):
        deleted_count, removed_reference_ids = await delete_project_file_with_cleanup(
            project_id, file_id, revision=1
        )

    assert deleted_count == 0
    assert removed_reference_ids == []
    unlink_mock.assert_not_awaited()
    clear_fetch_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_matches_still_clears_fetch_results():
    """A reference may have a fetch result (e.g. SourceFound pointing at file_id)
    even when no ReferenceFileMatching entry exists yet. The fetch-result cleanup
    must run regardless of whether the unlink step found anything."""
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())

    delete_mock = AsyncMock(return_value=1)
    unlink_mock = AsyncMock(return_value=[])
    clear_fetch_mock = AsyncMock(return_value=1)

    with (
        patch("lib.services.projects.delete_project_files", delete_mock),
        patch("lib.services.projects.remove_file_from_references", unlink_mock),
        patch("lib.services.projects.remove_fetch_result_for_file", clear_fetch_mock),
    ):
        deleted_count, removed_reference_ids = await delete_project_file_with_cleanup(
            project_id, file_id, revision=1
        )

    assert deleted_count == 1
    assert removed_reference_ids == []
    clear_fetch_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_revision_is_forwarded_to_cleanup_calls():
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    revision = 42

    unlink_mock = AsyncMock(return_value=[])
    clear_fetch_mock = AsyncMock(return_value=0)

    with (
        patch("lib.services.projects.delete_project_files", AsyncMock(return_value=1)),
        patch("lib.services.projects.remove_file_from_references", unlink_mock),
        patch("lib.services.projects.remove_fetch_result_for_file", clear_fetch_mock),
    ):
        await delete_project_file_with_cleanup(project_id, file_id, revision=revision)

    assert unlink_mock.await_args.kwargs["revision"] == revision
    assert clear_fetch_mock.await_args.kwargs["revision"] == revision
