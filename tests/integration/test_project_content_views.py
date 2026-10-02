"""The reads each tab fetches on demand: `/document`, `/issues`, `/references`
and the run history. Each must serve the revision asked for and skip whatever
stored data no longer reads."""

from unittest.mock import AsyncMock, patch

import pytest

from lib.api.routers.project_views import (
    get_project_document_endpoint,
    get_project_issues_endpoint,
    get_project_references_endpoint,
    get_project_workflow_runs_by_type_endpoint,
)
from tests.integration.project_page_support import (  # noqa: F401  # `page` is a fixture
    ASSESSMENT,
    overview_of,
    page,
)


@pytest.mark.asyncio
async def test_document_takes_title_and_authors_from_the_main_file_summary(page):
    document = await get_project_document_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )

    assert (document.title, document.authors) == ("The Draft", "A. Author")
    assert document.markdown is None  # no main file on record in this fixture


@pytest.mark.asyncio
async def test_document_reads_the_revisions_markdown(page):
    with patch(
        "lib.services.project_content.get_main_document_markdown",
        new=AsyncMock(return_value="# The Draft"),
    ) as markdown:
        document = await get_project_document_endpoint(
            page["project_id"], revision=1, share_token=None, current_user=page["owner"]
        )

    markdown.assert_awaited_once_with(page["project_id"], 1)
    assert document.markdown == "# The Draft"
    # Revision 1 was never summarized, so there is no title to show.
    assert (document.title, document.authors) == (None, None)


@pytest.mark.asyncio
async def test_issues_are_the_revisions_own(page):
    current = await get_project_issues_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )
    older = await get_project_issues_endpoint(
        page["project_id"], revision=1, share_token=None, current_user=page["owner"]
    )

    assert [issue.id for issue in current] == [page["issue_id"]]
    assert older == []


@pytest.mark.asyncio
async def test_archived_issues_are_neither_listed_nor_counted(page):
    issues = await get_project_issues_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )
    overview = await overview_of(page)

    assert [issue.id for issue in issues] == [page["issue_id"]]
    assert overview.issues_version.startswith("1:")


@pytest.mark.asyncio
async def test_references_drop_the_fetch_transcripts(page):
    references = await get_project_references_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )

    assert [ref.id for ref in references.extracted_references] == ["r1", "r2"]
    assert [f.reference_id for f in references.fetched_references] == ["r1"]
    assert references.fetched_references[0].messages == []


@pytest.mark.asyncio
async def test_references_keep_the_readable_matches(page):
    references = await get_project_references_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )

    assert [(m.reference_id, m.file_id) for m in references.matches] == [("r1", "f1")]


@pytest.mark.asyncio
async def test_history_lists_the_revisions_runs_newest_first(page):
    history = await get_project_workflow_runs_by_type_endpoint(
        page["project_id"],
        workflow_type=ASSESSMENT,
        revision=None,
        share_token=None,
        current_user=page["owner"],
    )

    assert len(history) == 2
    assert str(history[0].run.id) == page["assessment_id"]
    assert history[0].run.created_at > history[1].run.created_at


@pytest.mark.asyncio
async def test_history_follows_the_revision_asked_for(page):
    history = await get_project_workflow_runs_by_type_endpoint(
        page["project_id"],
        workflow_type=ASSESSMENT,
        revision=1,
        share_token=None,
        current_user=page["owner"],
    )

    assert len(history) == 1
    assert history[0].run.revision == 1
