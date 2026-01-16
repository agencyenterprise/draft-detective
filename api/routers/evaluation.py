"""
Evaluation package generation endpoints
"""

import logging

from fastapi import APIRouter, HTTPException

from lib.services.eval_generator.generator import (
    ChunkEvalPackageRequest,
    EvalPackageRequest,
    eval_test_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluation"])


@router.post("/api/generate-eval-package")
async def generate_eval_package(request: EvalPackageRequest):
    """
    Generate complete eval test package as downloadable zip.

    Args:
        request: Contains project_id and metadata for test generation

    Returns:
        Zip file containing YAML test files and data files
    """
    try:
        return await eval_test_generator.generate_package(
            project_id=request.project_id,
            test_name=request.test_name,
            description=request.description,
        )

    except Exception as e:
        logger.error(f"Error generating eval package: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error generating eval package: {str(e)}"
        )


@router.post("/api/generate-chunk-eval-package")
async def generate_chunk_eval_package(request: ChunkEvalPackageRequest):
    """
    Generate eval test package for a specific chunk with selected agents.
    Only includes files required by the selected agents.

    Args:
        request: Contains project_id, chunk index, selected agents, and metadata

    Returns:
        Optimized zip file containing only necessary YAML test files and data files
    """
    try:
        return await eval_test_generator.generate_chunk_package(
            project_id=request.project_id,
            chunk_index=request.chunk_index,
            selected_agents=request.selected_agents,
            test_name=request.test_name,
            description=request.description,
        )

    except ValueError as e:
        logger.error(f"Invalid request for chunk eval generation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating chunk eval package: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error generating chunk eval package: {str(e)}"
        )
