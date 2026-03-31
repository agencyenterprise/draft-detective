"""
Health check and system metadata endpoints
"""

import logging

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text

from lib.config.database import get_async_db_session

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)


@router.get("/api/health")
@router.head("/api/health")
async def read_health():
    """Health check endpoint — verifies database connectivity."""
    try:
        async with get_async_db_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database unavailable: {e}", exc_info=True)
        return Response(status_code=503, content=f"Database unavailable")

    return {"status": "healthy"}
