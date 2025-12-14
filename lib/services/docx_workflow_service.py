"""Service for managing DOCX generation workflow runs with caching."""

import logging
from pathlib import Path
from typing import Optional

from lib.config.env import config
from lib.models.user import User
from lib.workflows.docx_generation.state import (
    DocxGenerationWorkflowConfig,
    DocxGenerationState,
)
from lib.workflows.models import WorkflowRunType

logger = logging.getLogger(__name__)


def _get_cache_key(claim_run_id: str, share_token: Optional[str]) -> str:
    """Generate cache key for DOCX file."""
    suffix = "shared" if share_token else "base"
    return f"{claim_run_id}_{suffix}"


def _get_cached_docx_path(cache_key: str) -> Optional[Path]:
    """Check if cached DOCX exists and return path."""
    output_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
    cached_file = output_dir / f"{cache_key}_reviewed.docx"
    return cached_file if cached_file.exists() else None


async def get_or_generate_docx(
    claim_run_id: str,
    project_id: str,
    share_token: Optional[str],
    user: User,
) -> tuple[str, str]:
    """
    Get cached DOCX or generate new one via workflow.

    Returns:
        tuple[str, str]: (file_path, filename)
    """
    cache_key = _get_cache_key(claim_run_id, share_token)
    cached_path = _get_cached_docx_path(cache_key)

    if cached_path:
        logger.info(f"Serving cached DOCX for {cache_key}")
        from lib.services.workflow_runs import (
            get_workflow_run,
            get_workflow_run_state_by_thread_id,
        )

        claim_run = await get_workflow_run(claim_run_id)
        claim_state = await get_workflow_run_state_by_thread_id(
            claim_run.langgraph_thread_id, WorkflowRunType.CLAIM_SUBSTANTIATION
        )
        base_name = claim_state.file.file_name.rsplit(".", 1)[0]
        filename = f"{base_name}_reviewed.docx"
        return str(cached_path), filename

    logger.info(f"Cache miss for {cache_key}, generating DOCX via workflow")

    from lib.workflows.runner import run_workflow_from_config
    import uuid

    config = DocxGenerationWorkflowConfig(
        claim_substantiation_run_id=claim_run_id,
        share_token=share_token,
        project_id=project_id,
    )

    thread_id = str(uuid.uuid4())
    final_state: DocxGenerationState = await run_workflow_from_config(
        config=config, thread_id=thread_id, user=user
    )

    if not final_state.generated_file_path or not final_state.filename:
        raise ValueError("DOCX generation workflow completed without output")

    return final_state.generated_file_path, final_state.filename
