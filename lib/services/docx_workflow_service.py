"""Generate exported DOCX files (with comments or add-in metadata) on demand."""

import logging
import uuid
from typing import List, Literal, Optional

from lib.models.workflow_run import WorkflowRunType
from lib.services.docx.manipulator import (
    DocxManipulatorType,
    docx_manipulator_service,
    issue_to_comment,
)
from lib.services.docx.paragraph_line_mapper import build_paragraph_line_ranges
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.issue_persistence import get_project_issues
from lib.services.projects import _get_project_by_id
from lib.workflows.models import SeverityEnum

logger = logging.getLogger(__name__)


async def generate_docx(
    project_id: str,
    share_token: Optional[str],
    severities: Optional[List[SeverityEnum]] = None,
    workflow_types: Optional[List[WorkflowRunType]] = None,
    docx_type: DocxManipulatorType | Literal["original"] = DocxManipulatorType.COMMENTS,
    include_passing: bool = False,
) -> tuple[str, str]:
    """Generate an export of the project's DOCX.

    Always regenerates from scratch — there is no caching layer.

    Args:
        project_id: The project ID
        share_token: Optional share token for share links in comments
        severities: Optional list of severity levels to filter issues
        workflow_types: Optional list of workflow types to filter issues
        docx_type: The export variant. ``"original"`` returns the uploaded file
            untouched; ``COMMENTS`` / ``COMMENTS_WITH_LINKS`` / ``ADD_IN`` produce
            the corresponding processed variants.
        include_passing: Whether to include passing issues (severity=none)

    Returns:
        ``(file_path, filename)`` for the generated file.
    """
    project = await _get_project_by_id(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    revision = project.current_revision

    file_artifacts = FileArtifactsService(project_id, revision=revision)
    main_file = await file_artifacts.get_main_file()

    if docx_type == "original":
        logger.info(f"Serving original DOCX for {project_id}")
        return main_file.file_path, main_file.file_name

    # After the "original" early-return above, docx_type is a DocxManipulatorType.
    assert isinstance(docx_type, DocxManipulatorType)

    chunks = await file_artifacts.get_chunks()

    # Validate file is a DOCX
    main_file_path = main_file.file_path.lower()
    if not main_file_path.endswith(".docx") and not main_file_path.endswith(".doc"):
        raise ValueError("Main file must be a .docx or .doc to generate reviewed DOCX")

    # Build paragraph → (start_line, end_line) map via marker injection. This is
    # authoritative (no fuzzy matching) and resolves each issue's line range to a
    # target docx paragraph for both the comments and add-in flows.
    paragraph_line_ranges = await build_paragraph_line_ranges(main_file.file_path)

    # Query persisted issues directly from DB (faster than computing from workflow states)
    # get_project_issues excludes archived issues by default
    all_issues = list(
        await get_project_issues(
            project_id=uuid.UUID(project_id),
            revision=revision,
            workflow_types=workflow_types,
        )
    )

    # Exclude resolved issues from export
    issues = [issue for issue in all_issues if not issue.is_resolved]

    # Filter issues by severity if specified
    if severities:
        issues = [issue for issue in issues if issue.severity in severities]

    # Exclude passing issues (severity=none) unless explicitly included
    if not include_passing:
        issues = [issue for issue in issues if issue.severity != SeverityEnum.NONE]

    if not share_token:
        docx_type = DocxManipulatorType.COMMENTS

    # Unique per invocation so concurrent exports never collide.
    output_id = uuid.uuid4().hex

    if docx_type in [
        DocxManipulatorType.COMMENTS,
        DocxManipulatorType.COMMENTS_WITH_LINKS,
    ]:
        share_token_for_comments = (
            share_token
            if docx_type == DocxManipulatorType.COMMENTS_WITH_LINKS
            else None
        )
        comments = [
            c
            for issue in issues
            if (
                c := issue_to_comment(
                    issue,
                    chunks,
                    paragraph_line_ranges,
                    share_token_for_comments,
                )
            )
        ]
        output_path = await docx_manipulator_service.add_comments_to_docx(
            original_docx_path=main_file.file_path,
            comments=comments,
            workflow_run_id=output_id,
            docx_type=docx_type,
        )
    elif docx_type == DocxManipulatorType.ADD_IN:
        if share_token is None:
            raise ValueError("share_token is required for ADD_IN docx export")
        output_path = await docx_manipulator_service.add_addin_metadata_to_docx(
            original_docx_path=main_file.file_path,
            share_token=share_token,
            workflow_run_id=output_id,
            paragraph_line_ranges=paragraph_line_ranges,
            chunks=chunks,
            issues=issues,
        )
    else:
        raise ValueError(f"Unsupported docx_type: {docx_type}")

    base_name = main_file.file_name.rsplit(".", 1)[0]
    filename = f"{base_name}_{docx_type.value}.docx"
    return output_path, filename
