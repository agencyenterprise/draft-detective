import logging
from typing import List, Optional

from lib.config.langfuse import langfuse_handler
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.file import FileDocument
from lib.services.projects import get_user_project_detailed, update_project_title
from lib.services.workflow_runs import upsert_workflow_run
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.models import WorkflowError, WorkflowRunType
from lib.workflows.registry import create_context
from lib.workflows.runner import run_workflow

logger = logging.getLogger(__name__)


async def run_claim_substantiator(
    project_id: str,
    thread_id: str,
    file: FileDocument,
    supporting_files: Optional[List[FileDocument]] = None,
    config: SubstantiationWorkflowConfig = None,
) -> ClaimSubstantiatorState:
    """
    Claim substantiation runner using LangGraph approach.

    Supports both full document processing and selective chunk re-evaluation:
    - For full processing: leave config.target_chunk_indices and config.agents_to_run as None
    - For selective re-evaluation: provide config.target_chunk_indices and/or config.agents_to_run
    - For re-evaluation with existing results: provide existing_state to preserve previous results

    This is the single, authoritative entry point for claim substantiation.
    """

    if config is None:
        config = SubstantiationWorkflowConfig()

    context = create_context(config)
    config.openai_api_key = "[REDACTED]"
    state = ClaimSubstantiatorState(
        file=file,
        supporting_files=supporting_files,
        config=config,
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
    config.session_id = thread_id
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
