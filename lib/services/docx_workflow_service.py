"""Service for managing DOCX generation with caching."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from lib.config.env import config as env_config
from lib.services.docx.manipulator import docx_manipulator_service, issue_to_comment
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.issues import convert_to_issues
from lib.services.workflow_runs import get_project_workflow_runs

logger = logging.getLogger(__name__)


def get_cache_key(
    project_id: str, share_token: Optional[str], severities: Optional[List[str]] = None
) -> str:
    """Generate cache key for DOCX file."""
    suffix = "shared" if share_token else "base"
    if severities:
        # Sort for consistent cache keys regardless of order
        severity_suffix = "_".join(sorted(severities))
        return f"{project_id}_{suffix}_{severity_suffix}"
    return f"{project_id}_{suffix}"


def get_cached_docx_path(cache_key: str) -> Optional[Path]:
    """Check if cached DOCX exists and return path."""
    output_dir = Path(env_config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
    cached_file = output_dir / f"{cache_key}_reviewed.docx"
    return cached_file if cached_file.exists() else None


async def get_or_generate_docx(
    project_id: str,
    share_token: Optional[str],
    severities: Optional[List[str]] = None,
    use_cache: bool = True,
) -> tuple[str, str]:
    """
    Get cached DOCX or generate a new one.

    Args:
        project_id: The project ID
        share_token: Optional share token for share links in comments
        severities: Optional list of severity levels to filter issues (e.g., ["high", "medium"])
        use_cache: Whether to use cached version if available

    Returns:
        tuple[str, str]: (file_path, filename)
    """

    cache_key = get_cache_key(project_id, share_token, severities)
    cached_path = get_cached_docx_path(cache_key)
    file_artifacts_service = FileArtifactsService(project_id)

    if use_cache and cached_path:
        logger.info(f"Serving cached DOCX for {cache_key}")
        file_document = await file_artifacts_service.get_main_file()
        base_name = file_document.file_name.rsplit(".", 1)[0]
        filename = f"{base_name}_reviewed.docx"
        return str(cached_path), filename

    logger.info(f"Cache miss for {cache_key}, generating DOCX")
    return await generate_docx(project_id, share_token, severities)


async def generate_docx(
    project_id: str,
    share_token: Optional[str],
    severities: Optional[List[str]] = None,
) -> tuple[str, str]:
    """Generate a DOCX file with AI-generated comments from workflow issues and chunks.

    Args:
        project_id: The project ID
        share_token: Optional share token for share links in comments
        severities: Optional list of severity levels to filter issues (e.g., ["high", "medium"])

    Returns:
        tuple[str, str]: (file_path, filename)
    """

    # Get main file and chunks using FileArtifactsService
    file_artifacts = FileArtifactsService(project_id)
    main_file = await file_artifacts.get_main_file()
    chunks = await file_artifacts.get_chunks()

    # Validate file is a DOCX
    main_file_path = main_file.file_path.lower()
    if not main_file_path.endswith(".docx") and not main_file_path.endswith(".doc"):
        raise ValueError("Main file must be a .docx or .doc to generate reviewed DOCX")

    if share_token:
        output_path = await docx_manipulator_service.add_addin_metadata_to_docx(
            original_docx_path=main_file.file_path,
            project_id=project_id,
            share_token=share_token,
            chunks=chunks,
        )
    else:
        # Build chunk content map and convert workflow issues to comments
        chunk_content_map: Dict[int, str] = {c.chunk_index: c.content for c in chunks}

        workflow_runs = await get_project_workflow_runs(project_id)
        workflow_states = [run.state for run in workflow_runs if run.state is not None]
        issues = convert_to_issues(workflow_states)

        # Filter issues by severity if specified
        if severities:
            issues = [issue for issue in issues if issue.severity in severities]

        comments = [
            c
            for issue in issues
            if (c := issue_to_comment(issue, chunk_content_map, share_token))
        ]

        # Generate the DOCX with comments
        output_id = get_cache_key(project_id, share_token, severities)
        output_path = await docx_manipulator_service.add_comments_to_docx(
            original_docx_path=main_file.file_path,
            comments=comments,
            workflow_run_id=output_id,
            chunks=chunks,
        )

    base_name = main_file.file_name.rsplit(".", 1)[0]
    filename = f"{base_name}_reviewed.docx"
    return output_path, filename
