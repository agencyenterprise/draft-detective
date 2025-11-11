"""
Workflow run management endpoints
"""

import os
from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse

from lib.config.env import config
from lib.models.workflow_run import WorkflowRun
from lib.services.workflow_runs import (
    UpdateWorkflowRunRequest,
    WorkflowRunDetailed,
    delete_workflow_run,
    get_chunk_details,
    get_workflow_run_detailed,
    get_workflow_runs,
    update_workflow_run,
)
from lib.workflows.claim_substantiation.state import DocumentChunk

router = APIRouter(tags=["workflows"])


@router.get("/api/workflow-runs", response_model=list[WorkflowRun])
async def list_workflow_runs():
    """List all workflow runs"""
    return await get_workflow_runs()


@router.get("/api/workflow-run/{workflow_run_id}", response_model=WorkflowRunDetailed)
async def get_workflow_run(workflow_run_id: str):
    """Get detailed workflow run information including state"""
    return await get_workflow_run_detailed(workflow_run_id)


@router.patch("/api/workflow-run/{workflow_run_id}", response_model=WorkflowRun)
async def update_workflow_run_endpoint(
    workflow_run_id: str, request: UpdateWorkflowRunRequest
):
    """Update a workflow run with the provided fields"""
    return await update_workflow_run(workflow_run_id, request)


@router.get(
    "/api/workflow-run/{workflow_run_id}/chunk/{chunk_index}",
    response_model=DocumentChunk,
)
async def get_chunk_details_endpoint(workflow_run_id: str, chunk_index: int):
    """Get detailed analysis for a specific chunk (lazy loading)"""
    return await get_chunk_details(workflow_run_id, chunk_index)


@router.delete("/api/workflow-run/{workflow_run_id}")
async def delete_workflow_run_endpoint(workflow_run_id: str):
    """Delete a workflow run and its associated checkpoint data"""
    await delete_workflow_run(workflow_run_id)
    return {"message": "Workflow run deleted successfully", "id": workflow_run_id}


@router.get("/api/workflow-runs/{workflow_run_id}/pages/{image_path:path}")
async def get_page_image(workflow_run_id: str, image_path: str):
    """
    Serve Docling page images for a workflow run

    When Docling uses image_export_mode='reference', it downloads images
    from Docling-serve and stores them locally. This endpoint serves those images.

    Images are stored at: {uploads}/docling_images/{file_id}/{image_filename}
    where file_id is the xxhash of the document.

    Args:
        workflow_run_id: The workflow run ID
        image_path: The image filename from Docling (e.g., 'page_0.png')

    Returns:
        The image file
    """
    image_path = os.path.normpath(image_path).lstrip("/")
    if ".." in image_path:
        raise HTTPException(status_code=400, detail="Invalid image path")

    try:
        workflow_run = await get_workflow_run(workflow_run_id)

        if workflow_run.state and hasattr(workflow_run.state, "file"):
            file_path = workflow_run.state.file.file_path

            filename = os.path.basename(file_path)
            file_id, _ = os.path.splitext(filename)

            image_file_path = os.path.join(
                config.FILE_UPLOADS_MOUNT_PATH, "docling_images", file_id, image_path
            )

            if os.path.exists(image_file_path) and os.path.isfile(image_file_path):
                return FileResponse(
                    path=image_file_path,
                    media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"},
                )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Error looking up workflow state for images: {e}")

    possible_paths = [
        os.path.join(config.FILE_UPLOADS_MOUNT_PATH, workflow_run_id, image_path),
        os.path.join(config.FILE_UPLOADS_MOUNT_PATH, image_path),
    ]

    for file_path in possible_paths:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(
                path=file_path,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=3600"},
            )

    raise HTTPException(status_code=404, detail=f"Page image not found: {image_path}")
