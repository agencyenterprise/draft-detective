"""Service for managing DOCX generation with caching."""

import logging
import uuid
from pathlib import Path
from typing import List, Literal, Optional

from lib.config.env import config as env_config
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

# Bumped whenever the docx export format changes in a way that invalidates cached
# files on disk. Old cached files remain but are never served because the cache
# key no longer matches.
CACHE_VERSION = 2


def get_cache_key(
    project_id: str,
    share_token: Optional[str],
    severities: Optional[List[SeverityEnum]] = None,
    workflow_types: Optional[List[WorkflowRunType]] = None,
    include_passing: bool = False,
) -> str:
    """Generate cache key for DOCX file."""
    suffix = "shared" if share_token else "base"
    key = f"{project_id}_{suffix}_v{CACHE_VERSION}"
    if severities:
        severity_suffix = "_".join(sorted(s.value for s in severities))
        key = f"{key}_sev_{severity_suffix}"
    if workflow_types:
        workflow_suffix = "_".join(sorted(w.value for w in workflow_types))
        key = f"{key}_wf_{workflow_suffix}"
    if include_passing:
        key = f"{key}_passing"
    return key


def get_cached_docx_path(
    cache_key: str, docx_type: DocxManipulatorType = DocxManipulatorType.COMMENTS
) -> Optional[Path]:
    """Check if cached DOCX exists and return path."""
    output_dir = Path(env_config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
    cached_file = output_dir / f"{cache_key}_{docx_type.value}.docx"
    return cached_file if cached_file.exists() else None


async def get_or_generate_docx(
    project_id: str,
    share_token: Optional[str],
    severities: Optional[List[SeverityEnum]] = None,
    workflow_types: Optional[List[WorkflowRunType]] = None,
    docx_type: DocxManipulatorType | Literal["original"] = DocxManipulatorType.COMMENTS,
    include_passing: bool = False,
    use_cache: bool = True,
) -> tuple[str, str]:
    """
    Get cached DOCX or generate a new one.

    Args:
        project_id: The project ID
        share_token: Optional share token for share links in comments
        severities: Optional list of severity levels to filter issues
        workflow_types: Optional list of workflow types to filter issues
        include_passing: Whether to include passing issues (severity=none)
        use_cache: Whether to use cached version if available

    Returns:
        tuple[str, str]: (file_path, filename)
    """
    project = await _get_project_by_id(project_id)
    revision = project.current_revision if project else 1
    file_artifacts_service = FileArtifactsService(project_id, revision=revision)

    if docx_type == "original":
        logger.info(f"Serving original DOCX for {project_id}")
        file_document = await file_artifacts_service.get_main_file()
        return file_document.file_path, file_document.file_name

    cache_key = get_cache_key(
        project_id, share_token, severities, workflow_types, include_passing
    )
    cached_path = get_cached_docx_path(cache_key, docx_type)

    if use_cache and cached_path:
        logger.info(f"Serving cached DOCX for {cache_key}")
        file_document = await file_artifacts_service.get_main_file()
        base_name = file_document.file_name.rsplit(".", 1)[0]
        filename = f"{base_name}_{docx_type.value}.docx"
        return str(cached_path), filename

    logger.info(f"Cache miss for {cache_key}, generating DOCX")
    return await generate_docx(
        project_id, share_token, severities, workflow_types, docx_type, include_passing
    )


async def generate_docx(
    project_id: str,
    share_token: Optional[str],
    severities: Optional[List[SeverityEnum]] = None,
    workflow_types: Optional[List[WorkflowRunType]] = None,
    docx_type: DocxManipulatorType = DocxManipulatorType.COMMENTS,
    include_passing: bool = False,
) -> tuple[str, str]:
    """Generate a DOCX file with AI-generated comments from workflow issues and chunks.

    Args:
        project_id: The project ID
        share_token: Optional share token for share links in comments
        severities: Optional list of severity levels to filter issues
        workflow_types: Optional list of workflow types to filter issues
        docx_type: Docx type to generate
        include_passing: Whether to include passing issues (severity=none)

    Returns:
        tuple[str, str]: (file_path, filename)
    """

    # Resolve current revision for the project
    project = await _get_project_by_id(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    revision = project.current_revision

    # Get main file and chunks using FileArtifactsService
    file_artifacts = FileArtifactsService(project_id, revision=revision)
    main_file = await file_artifacts.get_main_file()
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

    output_path = None
    if not share_token:
        docx_type = DocxManipulatorType.COMMENTS

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

        output_id = get_cache_key(
            project_id,
            share_token_for_comments,
            severities,
            workflow_types,
            include_passing,
        )
        output_path = await docx_manipulator_service.add_comments_to_docx(
            original_docx_path=main_file.file_path,
            comments=comments,
            workflow_run_id=output_id,
            docx_type=docx_type,
        )

    elif docx_type == DocxManipulatorType.ADD_IN:
        output_id = get_cache_key(project_id, share_token)
        output_path = await docx_manipulator_service.add_addin_metadata_to_docx(
            original_docx_path=main_file.file_path,
            share_token=share_token,
            workflow_run_id=output_id,
            paragraph_line_ranges=paragraph_line_ranges,
            chunks=chunks,
            issues=issues,
        )

    base_name = main_file.file_name.rsplit(".", 1)[0]
    filename = f"{base_name}_{docx_type.value}.docx"
    return output_path, filename
