"""The heavier parts of the project page, each loaded only by the tab that reads it.

Both reads pick the few state fields they serve out of `state_json` in SQL
rather than hydrating whole states: the reference states are mostly agent
transcripts, and the summarization state holds a ~1000-word summary of every
supporting file when the page needs only the main document's title and authors.
"""

import logging
from typing import Any, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import WorkflowRun
from lib.services.projects import get_main_document_markdown
from lib.services.workflow_runs import latest_run_per_type_stmt
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_downloader.state import ReferenceFetchResult
from lib.workflows.reference_extraction.state import ExtractedReference
from lib.workflows.reference_file_matching.state import ReferenceFileMatch

logger = logging.getLogger(__name__)

_STATE = col(WorkflowRun.state_json)
_Item = TypeVar("_Item", bound=BaseModel)


class ProjectDocument(BaseModel):
    markdown: Optional[str] = Field(
        default=None,
        description="Full markdown of the main document, or null before processing completes",
    )
    title: Optional[str] = Field(
        default=None, description="The main document's title, from its summary"
    )
    authors: Optional[str] = Field(
        default=None, description="The main document's authors, from its summary"
    )


class ProjectReferences(BaseModel):
    extracted_references: List[ExtractedReference] = Field(default_factory=list)
    matches: List[ReferenceFileMatch] = Field(default_factory=list)
    fetched_references: List[ReferenceFetchResult] = Field(
        default_factory=list,
        description="Web fetch outcomes, without the fetching agent's transcript",
    )


def _validate_items(
    model: Type[_Item], raw: Any, drop: tuple[str, ...] = ()
) -> List[_Item]:
    """Validate a persisted list item by item, so one stale entry costs only itself."""
    if not isinstance(raw, list):
        return []
    items: List[_Item] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(
                model.model_validate({k: v for k, v in entry.items() if k not in drop})
            )
        except ValidationError as e:
            logger.warning("Skipping unreadable %s: %s", model.__name__, e)
    return items


async def _main_document_summary(project_id: str, revision: int) -> dict[str, Any]:
    stmt = (
        latest_run_per_type_stmt(project_id, revision)
        .where(col(WorkflowRun.type) == WorkflowRunType.DOCUMENT_SUMMARIZATION)
        .add_columns(
            _STATE["main_file_id"].astext.label("main_file_id"),
            _STATE["summaries"].label("summaries"),
        )
    )
    async with get_async_db_session() as session:
        row = (await session.execute(stmt)).first()
    if row is None:
        return {}
    _, main_file_id, summaries = row
    for summary in summaries if isinstance(summaries, list) else []:
        if isinstance(summary, dict) and summary.get("file_id") == main_file_id:
            return summary
    return {}


async def get_project_document(project_id: str, revision: int) -> ProjectDocument:
    summary = await _main_document_summary(project_id, revision)
    return ProjectDocument(
        markdown=await get_main_document_markdown(project_id, revision),
        title=summary.get("title"),
        authors=summary.get("authors"),
    )


async def get_project_references(project_id: str, revision: int) -> ProjectReferences:
    """The reference list as the References and Files tabs compose it."""
    stmt = (
        latest_run_per_type_stmt(project_id, revision)
        .where(
            col(WorkflowRun.type).in_(
                [
                    WorkflowRunType.REFERENCE_EXTRACTION,
                    WorkflowRunType.REFERENCE_FILE_MATCHING,
                    WorkflowRunType.REFERENCE_DOWNLOADER,
                ]
            )
        )
        .add_columns(
            _STATE["extracted_references"].label("extracted_references"),
            _STATE["matches"].label("matches"),
            _STATE["fetched_references"].label("fetched_references"),
        )
    )
    async with get_async_db_session() as session:
        rows = (await session.execute(stmt)).all()

    references = ProjectReferences()
    for run, extracted, matches, fetched in rows:
        if run.type == WorkflowRunType.REFERENCE_EXTRACTION:
            references.extracted_references = _validate_items(
                ExtractedReference, extracted
            )
        elif run.type == WorkflowRunType.REFERENCE_FILE_MATCHING:
            references.matches = _validate_items(ReferenceFileMatch, matches)
        elif run.type == WorkflowRunType.REFERENCE_DOWNLOADER:
            references.fetched_references = _validate_items(
                ReferenceFetchResult, fetched, drop=("messages",)
            )
    return references
