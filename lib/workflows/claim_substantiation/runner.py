import logging
from typing import List, Optional

from lib.models.user import User
from lib.services.file import FileDocument
from lib.services.projects import get_user_project_detailed
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import create_context
from lib.workflows.runner import run_workflow

logger = logging.getLogger(__name__)


async def rerun_analysis(
    project_id: str,
    config: SubstantiationWorkflowConfig,
    current_user: User,
) -> ClaimSubstantiatorState:
    """
    Re-evaluate a single chunk using unified LangGraph approach.
    """
    logger.info(
        f"Rerunning analysis with config: {config.model_dump(exclude_none=True)}"
    )

    project = await get_user_project_detailed(project_id, current_user)
    thread_id = project.workflow_run.run.langgraph_thread_id
    original_result = project.workflow_run.state

    context = create_context(config)
    config.openai_api_key = "[REDACTED]"
    state = original_result.model_copy(
        update={
            "config": config,
        }
    )

    graph = build_claim_substantiator_graph(config=config)
    return await run_workflow(
        project_id,
        WorkflowRunType.CLAIM_SUBSTANTIATION,
        graph,
        state,
        context,
        thread_id,
    )
