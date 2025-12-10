import logging

from langgraph.graph import StateGraph

from lib.config.langfuse import langfuse_handler
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.projects import update_project_title
from lib.services.workflow_runs import upsert_workflow_run
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.context import ContextSchema
from lib.workflows.models import BaseWorkflowConfig, WorkflowError
from lib.workflows.registry import (
    WorkflowStateType,
    create_context,
    create_graph,
    create_state,
)

logger = logging.getLogger(__name__)


async def run_workflow_from_config(
    config: BaseWorkflowConfig, thread_id: str, user: User
) -> WorkflowStateType:
    graph = create_graph(config.type)
    context = create_context(config, user=user)

    # Redact the OpenAI API key from the config so it doesn't get saved in the state
    config.openai_api_key = "[REDACTED]"

    state = await create_state(config)

    return await run_workflow(
        project_id=config.project_id,
        workflow_type=config.type,
        graph=graph,
        state=state,
        context=context,
        thread_id=thread_id,
    )


async def run_workflow(
    project_id: str,
    workflow_type: WorkflowRunType,
    graph: StateGraph,
    state: WorkflowStateType,
    context: ContextSchema,
    thread_id: str,
) -> WorkflowStateType:
    """
    Run a workflow using LangGraph, persisting the state to the database and associating with the workflow run.

    Args:
        project_id: The ID of the project that this workflow run should be associated with
        workflow_type: The type of the workflow
        graph: The LangGraph graph to run
        state: The initial state of the workflow
        context: The context of the workflow
        thread_id: The ID of the workflow thread, this is the LangGraph thread ID used by the checkpointer

    Returns:
        The updated state of the workflow
    """

    logger.info(
        f"Starting workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    workflow_run_id = await upsert_workflow_run(
        project_id=project_id,
        thread_id=thread_id,
        status=WorkflowRunStatus.RUNNING,
        type=workflow_type,
    )

    # Update the context with the workflow run ID so it's available to the workflow nodes
    context.workflow_run_id = workflow_run_id

    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer).with_config(
            {
                "run_name": f"{workflow_type.value}",
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_session_id": project_id},
            }
        )

        try:
            updated_state = state.model_copy(deep=True)

            async for values in app.astream(
                state,
                {"configurable": {"thread_id": thread_id}},
                stream_mode="values",
                context=context,
            ):
                updated_state = updated_state.model_copy(update=values)

                await upsert_workflow_run(
                    project_id=project_id,
                    thread_id=thread_id,
                    status=WorkflowRunStatus.RUNNING,
                    type=workflow_type,
                )

                # Update the project title if this is a claim substantiation workflow
                # TODO: remove this after we refactor the project creation flow
                if (
                    workflow_type == WorkflowRunType.CLAIM_SUBSTANTIATION
                    and updated_state.main_document_summary
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
                project_id=project_id,
                thread_id=thread_id,
                status=WorkflowRunStatus.COMPLETED,
                type=workflow_type,
            )

    logger.info(
        f"Completed workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    return updated_state
