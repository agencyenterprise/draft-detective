import logging

from langgraph.graph import StateGraph

from api.services.workflow_orchestration import wait_for_dependencies
from lib.config.env import config as env_config
from lib.config.langfuse import langfuse_handler
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.projects import update_project_title
from lib.services.vector_store import VectorStoreService
from lib.services.workflow_runs import upsert_workflow_run
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.context import ContextSchema
from lib.workflows.models import BaseWorkflowConfig, WorkflowError
from lib.workflows.registry import create_graph, create_state
from lib.workflows.types import WorkflowConfig, WorkflowState

logger = logging.getLogger(__name__)


async def run_workflow_with_dependency_check(
    config: WorkflowConfig, thread_id: str, user: User
) -> None:
    """
    Run a workflow after checking and waiting for its dependencies to complete.

    This function:
    1. Waits for all dependencies to complete
    2. Updates workflow status to RUNNING
    3. Executes the workflow
    """

    try:
        # Wait for dependencies to complete
        if config.project_id:
            await wait_for_dependencies(config.type, config.project_id)

        # Run the workflow
        await run_workflow_from_config(config=config, thread_id=thread_id, user=user)

    except Exception as e:
        logger.error(f"Error running workflow: {e}", exc_info=True)

        await upsert_workflow_run(
            project_id=config.project_id,
            thread_id=thread_id,
            status=WorkflowRunStatus.COMPLETED,
            type=config.type,
        )


async def run_workflow_from_config(
    config: WorkflowConfig, thread_id: str, user: User
) -> WorkflowState:
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
    state: WorkflowState,
    context: ContextSchema,
    thread_id: str,
) -> WorkflowState:
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
            # Clear all errors from previous runs
            updated_state = state.model_copy(deep=True, update={"errors": []})

            async for values in app.astream(
                updated_state,
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

                # Update the project title if this is a document processing workflow
                if (
                    workflow_type == WorkflowRunType.DOCUMENT_PROCESSING
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


def create_context(
    config: BaseWorkflowConfig,
    workflow_run_id: str | None = None,
    user: User | None = None,
) -> ContextSchema:
    """
    Create workflow context.

    Each workflow declares whether it requires an API key via requires_api_key().
    Workflows that don't use LLMs (data manipulation only) can return False.
    """

    openai_api_key = (
        config.openai_api_key
        or env_config.OPENAI_API_KEY
        or env_config.AZURE_OPENAI_API_KEY
    )

    # Check if workflow requires API key (defined by the workflow config itself)
    if not openai_api_key and config.requires_api_key():
        raise ValueError("No OpenAI API key found in config or environment variables")

    # Only initialize vector store if we have an API key (needed for embeddings)
    vector_store = (
        VectorStoreService(env_config.DATABASE_URL, openai_api_key)
        if openai_api_key
        else None
    )

    file_artifacts_service = FileArtifactsService(config.project_id)

    return ContextSchema(
        openai_api_key=openai_api_key,
        vector_store=vector_store,
        user_id=str(user.id) if user else None,
        project_id=config.project_id,
        workflow_run_id=workflow_run_id,
        file_artifacts_service=file_artifacts_service,
    )
