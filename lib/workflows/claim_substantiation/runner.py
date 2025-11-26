import logging
import uuid
from typing import List, Optional

from lib.config.env import config
from lib.config.langfuse import langfuse_handler
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.file import FileDocument
from lib.services.vector_store import VectorStoreService
from lib.services.workflow_runs import get_workflow_run_detailed, upsert_workflow_run
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


async def run_claim_substantiator(
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

    return await _execute(state, context)


async def rerun_analysis(
    workflow_run_id: str,
    config: SubstantiationWorkflowConfig,
    current_user: User,
) -> ClaimSubstantiatorState:
    """
    Re-evaluate a single chunk using unified LangGraph approach.
    """
    logger.info(
        f"Rerunning analysis with config: {config.model_dump(exclude_none=True)}"
    )

    workflow_run = await get_workflow_run_detailed(workflow_run_id, user=current_user)
    original_result = workflow_run.state

    context = create_context(config)
    config.openai_api_key = "[REDACTED]"
    state = original_result.model_copy(
        update={
            "config": config,
        }
    )

    return await _execute(state, context)


async def _execute(state: ClaimSubstantiatorState, context: ContextSchema):
    """
    Execute the claim substantiation workflow.

    Note: If reusing a session_id from a previous run with a different graph structure,
    checkpoints may cause unexpected behavior. Use a fresh session_id after graph changes.
    """
    graph = build_claim_substantiator_graph(
        use_toulmin=state.config.use_toulmin,
        run_literature_review=state.config.run_literature_review,
        run_suggest_citations=state.config.run_suggest_citations,
        use_rag=state.config.use_rag,
        run_live_reports=state.config.run_live_reports,
        run_reference_validation=state.config.run_reference_validation,
    )

    # Generate a fresh session ID if not provided to avoid checkpoint conflicts
    if state.config.session_id is None:
        state.config.session_id = str(uuid.uuid4())
        logger.info("Generated new session ID: %s", state.config.session_id)

    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer).with_config(
            {
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_session_id": state.config.session_id},
            }
        )

        workflow_run_id = await upsert_workflow_run(
            session_id=state.config.session_id,
            status=WorkflowRunStatus.RUNNING,
            title=state.file.file_name,
        )

        state.workflow_run_id = workflow_run_id
        updated_state = state

        try:
            async for values in app.astream(
                state,
                {"configurable": {"thread_id": state.config.session_id}},
                stream_mode="values",
                context=context,
            ):
                updated_state = ClaimSubstantiatorState(**values)

                await upsert_workflow_run(
                    session_id=state.config.session_id,
                    status=WorkflowRunStatus.RUNNING,
                    title=(
                        updated_state.main_document_summary.title
                        if updated_state.main_document_summary
                        and updated_state.main_document_summary.title
                        else None
                    ),
                )
        except Exception as e:
            logger.error(f"Error streaming state: {e}", exc_info=True)
            updated_state.errors.append(WorkflowError(task_name="global", error=str(e)))
        finally:
            await upsert_workflow_run(
                session_id=state.config.session_id,
                status=WorkflowRunStatus.COMPLETED,
            )

    return updated_state


def create_context(workflow_config: SubstantiationWorkflowConfig) -> ContextSchema:
    """
    Create a context object for the langchain workflow.
    """

    openai_api_key = (
        workflow_config.openai_api_key
        or config.OPENAI_API_KEY
        or config.AZURE_OPENAI_API_KEY
    )

    if not openai_api_key:
        raise ValueError("No OpenAI API key found in config or environment variables")

    return ContextSchema(
        openai_api_key=openai_api_key,
        vector_store=VectorStoreService(config.DATABASE_URL, openai_api_key),
    )
