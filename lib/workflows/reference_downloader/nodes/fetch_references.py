import logging

from langchain_core.messages import BaseMessage
from langgraph.runtime import Runtime
from langgraph.types import Send

from lib.models.file import FileRole
from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.services.files.service import (
    delete_project_files,
    get_supporting_candidate_files,
    update_files_role,
)
from lib.services.markdown_conversion import convert_and_cache_file_markdown
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetchConclusion,
    ReferenceFetcherAgent,
    ReferenceFetcherAgentInput,
)
from lib.workflows.reference_downloader.fetch_logging import (
    log_fetch_outcome,
    log_run_summary,
    short_reference,
)
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderInputItem,
    ReferenceDownloaderState,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)
from lib.workflows.reference_file_matching.state import MatchSource

logger = logging.getLogger(__name__)


@register_node("Initialize references")
async def initialize_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Initialize all references with PENDING status immediately.

    This allows the frontend to display all references right away
    before any fetching has started.

    When the caller did not supply an explicit `references` list, default to
    every extracted reference that does not yet have a matched supporting
    file.
    """
    references = state.config.references
    source = "explicit config"
    if references is None:
        source = "unmatched extracted references"
        references = await _load_unmatched_references(
            runtime.context.file_artifacts_service
        )
    logger.info(
        "Reference downloader for project %s: %d references to fetch (from %s)",
        runtime.context.project_id,
        len(references),
        source,
    )

    pending_results = [
        ReferenceFetchResult(
            reference_id=ref.reference_id,
            input_reference=ref.text,
            status=ReferenceFetchStatus.PENDING,
        )
        for ref in references
    ]

    # Rely on the merge_fetch_results reducer so prior results for references NOT in this run
    # (e.g. when fetching a single reference) are preserved.
    return {"fetched_references": pending_results}


async def _load_unmatched_references(
    file_artifacts_service: FileArtifactsServiceType,
) -> list[ReferenceDownloaderInputItem]:
    """Fetch every extracted reference that does not yet have a matched file."""
    references = await file_artifacts_service.get_references()

    return [
        ReferenceDownloaderInputItem(reference_id=ref.reference_id, text=ref.text)
        for ref in references
        if not ref.has_associated_supporting_document and ref.reference_id is not None
    ]


@register_node("Distribute references")
async def distribute_references(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Fan-out node: creates a Send for each reference initialized as PENDING."""
    return [
        Send(
            "fetch_single_reference",
            {"reference": ref.input_reference, "reference_id": ref.reference_id},
        )
        for ref in state.fetched_references
        if ref.status == ReferenceFetchStatus.PENDING
    ]


@register_node("Fetch reference")
async def fetch_single_reference(state: dict, runtime: Runtime[ContextSchema]):
    """Process a single reference and return status update.

    Each call to this node handles one reference and returns an update
    that the reducer will merge into the state by reference_id.
    """
    reference = state["reference"]
    reference_id = state["reference_id"]

    agent = ReferenceFetcherAgent(runtime.context)

    project_id = runtime.context.project_id
    result = None
    error = None
    status = ReferenceFetchStatus.COMPLETED
    messages: list[BaseMessage] = []

    try:
        result, messages = await agent.ainvoke(
            ReferenceFetcherAgentInput(reference=reference)
        )
        log_fetch_outcome(reference, result, messages)

        if (
            result
            and result.final_conclusion != ReferenceFetchConclusion.SOURCE_FOUND
            and result.file_id
        ):
            # Sometimes the LLM will return a file ID for a non-found reference, so we need to clean it up
            logger.warning(
                "Reference %r concluded %s but carried file_id %s; dropping the file id",
                short_reference(reference),
                result.final_conclusion.value,
                result.file_id,
            )
            result.file_id = None

        if status == ReferenceFetchStatus.COMPLETED and result and result.file_id:
            # Promote file immediately (from SUPPORTING_CANDIDATE to SUPPORT)
            await update_files_role([result.file_id], FileRole.SUPPORT)
            # Convert and cache markdown now so
            # file_artifacts_service.get_project_files() serves the new file
            # from the DB cache. Without this, consumers such as
            # claim_reference_validation_v2 would have to convert the file's
            # markdown on demand on every read.
            try:
                await convert_and_cache_file_markdown(result.file_id)
            except Exception as exc:
                logger.warning(
                    "Failed to cache markdown for downloaded file %s: %s",
                    result.file_id,
                    exc,
                    exc_info=True,
                )
            # Update the reference file matching in the ReferenceExtraction workflow state
            await _update_reference_file_matching(
                project_id, result.file_id, reference_id, runtime.context.revision
            )

    except Exception as e:
        logger.error(
            "Error fetching reference %r: %s: %s",
            short_reference(reference),
            type(e).__name__,
            e,
            exc_info=True,
        )
        status = ReferenceFetchStatus.ERROR
        error = str(e)

    return {
        "fetched_references": [
            ReferenceFetchResult(
                reference_id=reference_id,
                input_reference=reference,
                status=status,
                result=result,
                error=error,
                messages=messages,
            )
        ]
    }


@register_node("Cleanup")
async def cleanup_failed_resources(
    state: ReferenceDownloaderState, runtime: Runtime[ContextSchema]
):
    """Clean up files for failed references and promote successful ones."""
    project_id = runtime.context.project_id
    fetched_references = state.fetched_references

    if not fetched_references:
        return {}

    valid_file_ids = {
        item.result.file_id
        for item in fetched_references
        if item.result
        and item.result.file_id
        and item.result.final_conclusion == ReferenceFetchConclusion.SOURCE_FOUND
    }

    candidate_files = await get_supporting_candidate_files(project_id)

    files_to_delete: list[str] = []
    files_to_promote: list[str] = []

    for f in candidate_files:
        file_id = str(f.id)
        if file_id in valid_file_ids:
            files_to_promote.append(file_id)
        else:
            files_to_delete.append(file_id)

    log_run_summary(project_id, fetched_references)

    if files_to_delete:
        deleted_count = await delete_project_files(project_id, files_to_delete)
        logger.info(
            "Deleted %d unlinked candidate files for project %s: %s",
            deleted_count,
            project_id,
            ", ".join(files_to_delete),
        )
        if deleted_count != len(files_to_delete):
            logger.warning(
                f"Deleted {deleted_count} files, but expected {len(files_to_delete)}"
            )

    if files_to_promote:
        await update_files_role(files_to_promote, FileRole.SUPPORT)
        logger.info(
            f"Promoted {len(files_to_promote)} reference files to SUPPORT for project {project_id}"
        )

    return {}


async def _update_reference_file_matching(
    project_id: str, file_id: str, reference_id: str, revision: int
):
    """Link the fetched file to its reference in the ReferenceFileMatching workflow state."""

    from lib.services.references import add_file_to_reference  # noqa: PLC0415  circular: references -> registry -> this node

    await add_file_to_reference(
        project_id=project_id,
        file_id=file_id,
        reference_id=reference_id,
        source=MatchSource.AUTO_FETCHED,
        revision=revision,
    )
