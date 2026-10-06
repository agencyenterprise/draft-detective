"""`/overview` and the public share endpoint that returns it.

The overview is what the project page polls: it must carry what the chrome
reads (each run's own errors, the reference count, whether the main file is
Word, the share status for the owner) and no run state.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import col

from lib.api.routers.public import get_shared_resource
from lib.config.database import get_async_db_session
from lib.models.issue import Issue
from lib.models.project import AccessLevel
from lib.workflows.models import WorkflowRunType
from tests.integration.project_page_support import (  # noqa: F401  # `page` is a fixture
    ASSESSMENT,
    RETIRED_TYPE,
    disable_share_link,
    overview_of,
    page,
)


@pytest.mark.asyncio
async def test_overview_carries_what_the_chrome_reads_and_no_state(page):
    overview = await overview_of(page)

    assert overview.access_level == AccessLevel.WRITE
    assert overview.revision == 2
    assert overview.reference_count == 2
    assert overview.has_docx is True
    # One run per type, the latest of the assessment.
    types = [summary.run.type for summary in overview.workflow_runs]
    assert sorted(types) == sorted(set(types))
    assessment = next(s for s in overview.workflow_runs if s.run.type == ASSESSMENT)
    assert str(assessment.run.id) == page["assessment_id"]
    assert [error.error for error in assessment.errors] == ["mine"]
    assert "state" not in overview.model_dump()["workflow_runs"][0]


@pytest.mark.asyncio
async def test_issues_version_moves_when_an_issue_changes(page):
    before = (await overview_of(page)).issues_version

    async with get_async_db_session() as session:
        await session.execute(
            update(Issue)
            .where(col(Issue.id) == page["issue_id"])
            .values(resolved_at=datetime.now(UTC))
        )
        await session.commit()

    assert (await overview_of(page)).issues_version != before


@pytest.mark.asyncio
async def test_overview_follows_the_revision_asked_for(page):
    overview = await overview_of(page, revision=1)

    assert overview.revision == 1
    assert [s.run.type for s in overview.workflow_runs] == [ASSESSMENT]
    assert overview.reference_count == 0


@pytest.mark.asyncio
async def test_overview_never_surfaces_retired_workflows(page):
    overview = await overview_of(page)

    assert RETIRED_TYPE not in [str(s.run.type) for s in overview.workflow_runs]
    assert all(isinstance(s.run.type, WorkflowRunType) for s in overview.workflow_runs)


@pytest.mark.asyncio
async def test_a_revision_without_processing_is_not_word(page):
    assert (await overview_of(page, revision=1)).has_docx is False


@pytest.mark.asyncio
async def test_share_token_reads_and_strangers_do_not(page):
    shared = await overview_of(page, share_token=page["token"], current_user=None)
    assert shared.access_level == AccessLevel.READ

    with pytest.raises(HTTPException) as exc:
        await overview_of(page, current_user=page["stranger"])
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_only_the_owner_sees_the_share_status(page):
    owned = await overview_of(page)
    shared = await overview_of(page, share_token=page["token"], current_user=None)

    assert owned.share_status is not None
    assert owned.share_status.enabled is True
    assert owned.share_status.share_link is not None
    assert owned.share_status.share_link.token == page["token"]
    assert shared.share_status is None


@pytest.mark.asyncio
async def test_share_status_reports_a_disabled_link(page):
    await disable_share_link(page)

    overview = await overview_of(page)

    assert overview.share_status is not None
    assert overview.share_status.enabled is False
    assert overview.share_status.share_link is None


@pytest.mark.asyncio
async def test_public_share_is_read_only_overview(page):
    overview = await get_shared_resource(page["token"])

    assert overview.access_level == AccessLevel.READ
    assert str(overview.project.id) == page["project_id"]
    # The link is the owner's to manage; whoever holds it is not shown it.
    assert overview.share_status is None


@pytest.mark.asyncio
async def test_public_share_rejects_unknown_and_disabled_links(page):
    with pytest.raises(HTTPException) as unknown:
        await get_shared_resource("not-a-real-token")
    assert unknown.value.status_code == 404

    await disable_share_link(page)

    with pytest.raises(HTTPException) as disabled:
        await get_shared_resource(page["token"])
    assert disabled.value.status_code == 404


@pytest.mark.asyncio
async def test_public_share_serves_only_projects(page):
    with pytest.raises(HTTPException) as exc:
        await get_shared_resource(page["other_token"])
    assert exc.value.status_code == 400
