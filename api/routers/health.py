"""
Health check and system metadata endpoints
"""

from fastapi import APIRouter

from lib.agents.registry import AgentInfo, agent_registry

router = APIRouter(tags=["health"])


@router.get("/api/health")
def read_health():
    """Health check endpoint"""
    return {"status": "healthy"}


@router.get("/api/supported-agents", response_model=list[AgentInfo])
async def get_supported_agents():
    """
    Get list of supported agent types for chunk re-evaluation.

    Returns:
        List of AgentInfo objects
    """
    return agent_registry.get_agents_info()
