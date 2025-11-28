import os

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from api.auth import get_current_user
from lib.config.env import config
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.docx_manipulator import docx_manipulator_service
from lib.services.workflow_runs import (
    WorkflowRunDetailed,
    get_chunk_details,
    get_workflow_run_detailed,
    get_workflow_runs,
)
from lib.workflows.claim_substantiation.state import DocumentChunk

router = APIRouter(tags=["workflows"])


@router.get("/api/workflow-runs", response_model=list[WorkflowRun])
async def list_workflow_runs(current_user: User = Depends(get_current_user)):
    """List all workflow runs"""
    return await get_workflow_runs(user=current_user)


@router.get("/api/workflow-run/{workflow_run_id}", response_model=WorkflowRunDetailed)
async def get_workflow_run(
    workflow_run_id: str, current_user: User = Depends(get_current_user)
):
    """Get detailed workflow run information including state"""
    return await get_workflow_run_detailed(workflow_run_id, user=current_user)


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
    current_user: User = Depends(get_current_user),
):
    """
    Serve Docling page images for a workflow run.

    Args:
        workflow_run_id: The workflow run ID
        page_num: The page number (e.g., 0, 1, 2, etc.)

    Returns:
        The image file for the specified page (PNG, JPEG, WEBP, etc.)
    """
    if page_num < 0:
        raise HTTPException(status_code=400, detail="Invalid page number")

    workflow_run = await get_workflow_run_detailed(workflow_run_id, user=current_user)

    if not workflow_run.state or not hasattr(workflow_run.state, "file"):
        raise HTTPException(status_code=404, detail="Workflow state not found")

    file_path = workflow_run.state.file.file_path
    filename = os.path.basename(file_path)
    file_id, _ = os.path.splitext(filename)

    images_dir = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, "docling_images", file_id)

    # Page images are always PNG (other artifacts may vary)
    image_file_path = os.path.join(images_dir, f"page_{page_num}.png")

    if os.path.exists(image_file_path):
        return FileResponse(
            path=image_file_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    raise HTTPException(status_code=404, detail=f"Page {page_num} not found")


@router.get("/api/workflow-runs/{workflow_run_id}/docx/download")
async def download_docx(
    workflow_run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download DOCX file - reviewed version if available, otherwise original"""

    workflow_run = await get_workflow_run_detailed(workflow_run_id, user=current_user)

    if not workflow_run.state or not workflow_run.state.file:
        raise HTTPException(status_code=404, detail="Workflow state not found")

    original_file_path = workflow_run.state.file.original_file_path
    if not original_file_path or not original_file_path.endswith(".docx"):
        raise HTTPException(
            status_code=404,
            detail="No DOCX file available for this workflow",
        )

    # Try to get reviewed version first
    reviewed_path = docx_manipulator_service.get_output_path(workflow_run_id)
    if reviewed_path.exists():
        file_path = str(reviewed_path)
        is_reviewed = True
    else:
        # Fall back to original
        file_path = original_file_path
        is_reviewed = False

    base_name, _ = os.path.splitext(workflow_run.state.file.file_name)
    filename = f"{base_name}_reviewed.docx" if is_reviewed else f"{base_name}.docx"

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
