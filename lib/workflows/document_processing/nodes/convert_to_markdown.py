import logging

from langgraph.runtime import Runtime

from lib.models.file import FileRole
from lib.run_utils import run_tasks
from lib.services.file import FileDocument
from lib.services.files import update_file_artifacts
from lib.services.markdown_conversion import convert_file_document_to_markdown
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node("Convert to markdown")
async def convert_to_markdown(
    state: DocumentProcessingState, runtime: Runtime[ContextSchema]
):
    main_file = state.file
    supporting = state.supporting_files or []

    # Main file first (sequentially) — the rest of the pipeline can't proceed
    # without it, so a failure here must abort the workflow.
    main_result = await _convert_and_persist(main_file, role=FileRole.MAIN)
    if isinstance(main_result, Exception):
        logger.error(
            f"Main document conversion failed for {main_file.file_name} "
            f"(file_id={main_file.file_id}): {main_result}"
        )
        raise main_result
    converted_main = main_result

    # Supporting files run with bounded concurrency. Failures are reported
    # per-file via WorkflowError but do not abort the workflow — downstream
    # nodes work from whichever supporting files converted successfully.
    results, errors = await run_tasks(
        [_convert_and_persist(f, role=FileRole.SUPPORT) for f in supporting],
        desc="Converting supporting documents",
        max_concurrent=8,
    )

    converted_supporting: list[FileDocument] = []
    workflow_errors: list[WorkflowError] = []
    workflow_run_id = runtime.context.workflow_run_id

    for original, result, error in zip(supporting, results, errors):
        # `_convert_and_persist` never raises — it returns the exception so
        # `run_tasks` produces a result, never an entry in `errors`. We still
        # check `error` defensively in case run_tasks itself produced one.
        failure: BaseException | None = error
        if isinstance(result, Exception):
            failure = result
        elif isinstance(result, FileDocument):
            converted_supporting.append(result)

        if failure is not None:
            workflow_errors.append(
                WorkflowError(
                    task_name="convert_to_markdown",
                    error=(
                        f"Failed to convert supporting file {original.file_name} "
                        f"(file_id={original.file_id}): {failure}"
                    ),
                    workflow_run_id=workflow_run_id,
                )
            )

    if workflow_errors:
        logger.warning(
            f"{len(workflow_errors)}/{len(supporting)} supporting documents "
            f"failed to convert; continuing with {len(converted_supporting)} "
            f"successful conversions"
        )

    return {
        "file": converted_main,
        "supporting_files": converted_supporting,
        "errors": workflow_errors,
    }


async def _convert_and_persist(
    file_document: FileDocument,
    role: FileRole = FileRole.MAIN,
) -> FileDocument | Exception:
    """Convert a single file to markdown and cache the result in the DB.

    Persisting incrementally (rather than waiting for every file in the batch
    to finish) means a worker restart mid-conversion doesn't throw away the
    work already completed: `convert_file_document_to_markdown` short-circuits
    when the cached markdown is already present.

    Returns the converted FileDocument on success, or the exception on failure.
    Returning instead of raising lets the caller report per-file errors
    without aborting the rest of the batch.
    """
    try:
        converted = await convert_file_document_to_markdown(
            file_document, role=role
        )
    except Exception as exc:
        logger.error(
            f"Markdown conversion failed for {file_document.file_name} "
            f"(file_id={file_document.file_id}): {exc}",
            exc_info=True,
        )
        return exc

    if converted.markdown:
        await update_file_artifacts(
            file_id=converted.file_id, markdown=converted.markdown
        )
    return converted
