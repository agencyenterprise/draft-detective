"""Converted markdown is blanked before a run's state goes to an MCP agent.

The document-processing state carries every converted document in full, and
the agent reading a run through get_workflow_run has no use for any of it.
"""

from lib.services.file import FileDocument
from lib.services.projects import strip_converted_markdown
from lib.services.workflow_runs.service import WorkflowRunDetail
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)


def _document(file_id: str) -> FileDocument:
    return FileDocument(
        file_id=file_id,
        file_name=f"{file_id}.md",
        file_path=f"/uploads/{file_id}.md",
        file_type="text/markdown",
        markdown=f"# {file_id}",
        markdown_token_count=1,
    )


def test_blanks_every_converted_document():
    state = DocumentProcessingState(
        config=DocumentProcessingWorkflowConfig(project_id="project"),
        file=_document("main"),
        supporting_files=[_document("source"), _document("other-source")],
    )
    # The stripping reads only `state`; the run metadata is irrelevant here.
    run = WorkflowRunDetail.model_construct(state=state)

    strip_converted_markdown([run])

    documents = [state.file, *(state.supporting_files or [])]
    assert [d.markdown for d in documents] == [None, None, None]
