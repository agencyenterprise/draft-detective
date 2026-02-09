"""
Health check and system metadata endpoints
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
@router.head("/api/health")
def read_health():
    """Health check endpoint"""
    return {"status": "healthy"}
