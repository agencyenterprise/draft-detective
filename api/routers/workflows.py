import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from api.auth import get_current_user, get_current_user_optional
from lib.config.database import get_db
from lib.config.env import config
from lib.models.share_link import ShareLink
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.workflow_runs import get_chunk_details, get_workflow_run_state
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)

router = APIRouter(tags=["workflows"])


def _check_share_access(workflow_run_id: str) -> None:
    """
    Check if workflow run's project has an active share link.

    Raises:
        HTTPException: 404 if workflow run not found, 401 if no active share link
    """
    with get_db() as db:
        workflow_run = (
            db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).first()
        )
        if not workflow_run:
            raise HTTPException(status_code=404, detail="Workflow run not found")

        share_link = (
            db.query(ShareLink)
            .filter(
                ShareLink.resource_type == "project",
                ShareLink.resource_id == workflow_run.project_id,
                ShareLink.is_active == True,
            )
            .first()
        )

        if not share_link:
            raise HTTPException(status_code=401, detail="Not authenticated")


@router.get(
    "/api/workflow-run/{workflow_run_id}/chunk/{chunk_index}",
    response_model=DocumentChunk,
)
async def get_chunk_details_endpoint(workflow_run_id: str, chunk_index: int):
    """Get detailed analysis for a specific chunk (lazy loading)"""
    return await get_chunk_details(workflow_run_id, chunk_index)


@router.get("/api/workflow-runs/{workflow_run_id}/pages/{page_num}")
async def get_page_image(
    workflow_run_id: str,
    page_num: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Serve Docling page images for a workflow run.

    Allows access if user is authenticated OR if the project has sharing enabled.

    Args:
        workflow_run_id: The workflow run ID
        page_num: The page number (e.g., 0, 1, 2, etc.)

    Returns:
        The image file for the specified page (PNG, JPEG, WEBP, etc.)
    """
    if page_num < 0:
        raise HTTPException(status_code=400, detail="Invalid page number")

    if current_user:
        state = await get_workflow_run_state(workflow_run_id, user=current_user)
    else:
        _check_share_access(workflow_run_id)
        state = await get_workflow_run_state(workflow_run_id, user=None)

    if not hasattr(state, "file"):
        raise HTTPException(status_code=404, detail="Workflow state not found")

    file_path = state.file.file_path
    filename = os.path.basename(file_path)
    file_id, _ = os.path.splitext(filename)

    images_dir = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, "docling_images", file_id)
    image_file_path = os.path.join(images_dir, f"page_{page_num}.png")

    if os.path.exists(image_file_path):
        return FileResponse(
            path=image_file_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    raise HTTPException(status_code=404, detail=f"Page {page_num} not found")
