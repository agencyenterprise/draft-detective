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

    return await _execute(project_id, thread_id, state, context)


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

    return await _execute(project_id, thread_id, state, context)


async def _execute(
    project_id: str,
    thread_id: str,
    state: ClaimSubstantiatorState,
    context: ContextSchema,
):
    """
    Execute the claim substantiation workflow.

    Note: If reusing a thread_id from a previous run with a different graph structure,
    checkpoints may cause unexpected behavior. Use a fresh thread_id after graph changes.
    """

    graph = build_claim_substantiator_graph(
        use_toulmin=state.config.use_toulmin,
        run_literature_review=state.config.run_literature_review,
        run_suggest_citations=state.config.run_suggest_citations,
        use_rag=state.config.use_rag,
        run_live_reports=state.config.run_live_reports,
        run_reference_validation=state.config.run_reference_validation,
    )

    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer).with_config(
            {
                "run_name": WorkflowRunType.CLAIM_SUBSTANTIATION.value,
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_session_id": project_id},
            }
        )

        workflow_run_id = await upsert_workflow_run(
            thread_id=thread_id,
            project_id=project_id,
            status=WorkflowRunStatus.RUNNING,
            type=WorkflowRunType.CLAIM_SUBSTANTIATION,
        )

        state.workflow_run_id = workflow_run_id
        updated_state = state

        try:
            async for values in app.astream(
                state,
                {"configurable": {"thread_id": thread_id}},
                stream_mode="values",
                context=context,
            ):
                updated_state = ClaimSubstantiatorState(**values)

                await upsert_workflow_run(
                    thread_id=thread_id,
                    project_id=project_id,
                    status=WorkflowRunStatus.RUNNING,
                    type=WorkflowRunType.CLAIM_SUBSTANTIATION,
                )

                if (
                    updated_state.main_document_summary
                    and updated_state.main_document_summary.title
                ):
                    await update_project_title(
                        project_id=project_id,
                        title=updated_state.main_document_summary.title,
                    )

        except Exception as e:
            logger.error(f"Error streaming state: {e}", exc_info=True)
            updated_state.errors.append(WorkflowError(task_name="global", error=str(e)))
        finally:
            await upsert_workflow_run(
                thread_id=thread_id,
                project_id=project_id,
                status=WorkflowRunStatus.COMPLETED,
                type=WorkflowRunType.CLAIM_SUBSTANTIATION,
            )

    return updated_state
