import logging
import uuid

from langgraph.graph import StateGraph

from api.services.workflow_orchestration import wait_for_dependencies
from lib.config.env import config as env_config
from lib.config.langfuse import langfuse_handler
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunStatus, WorkflowRunType
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.issue_persistence import persist_workflow_issues
from lib.services.vector_store import VectorStoreService
from lib.services.workflow_runs import update_workflow_run_status
from lib.workflows.checkpointer import get_checkpointer
from lib.workflows.context import ContextSchema
from lib.workflows.models import BaseWorkflowConfig, WorkflowError
from lib.workflows.registry import create_graph, create_state, get_workflow_manifest
from lib.workflows.types import WorkflowConfig, WorkflowState

logger = logging.getLogger(__name__)


async def run_workflow_with_dependency_check(
    config: WorkflowConfig, thread_id: str, workflow_run_id: str, user: User
) -> None:
    """
    Run a workflow after checking and waiting for its dependencies to complete.

    This function:
    1. Waits for any same-type workflow and dependencies to complete
    2. Executes the workflow

    Args:
        config: The workflow config to run
        thread_id: The LangGraph thread ID for checkpointing
        workflow_run_id: The unique ID of this workflow run (for same-type locking)
        user: The user running the workflow
    """

    try:
        if config.project_id:
            # Wait for same-type lock and dependencies to complete
            await wait_for_dependencies(
                config.type,
                config.project_id,
                workflow_run_id,
            )

        # Run the workflow
        await run_workflow_from_config(
            config=config,
            thread_id=thread_id,
            workflow_run_id=workflow_run_id,
            user=user,
        )

    except Exception as e:
        logger.error(f"Error running workflow: {e}", exc_info=True)
        await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.COMPLETED)


async def run_workflow_from_config(
    config: WorkflowConfig, thread_id: str, workflow_run_id: str, user: User
) -> WorkflowState:
    graph = create_graph(config.type)
    context = create_context(config, workflow_run_id=workflow_run_id, user=user)

    # Redact the OpenAI API key from the config so it doesn't get saved in the state
    config.openai_api_key = "[REDACTED]"

    state = await create_state(config)

    return await run_workflow(
        workflow_run_id=workflow_run_id,
        workflow_type=config.type,
        graph=graph,
        state=state,
        context=context,
        thread_id=thread_id,
    )


async def run_workflow(
    workflow_run_id: str,
    workflow_type: WorkflowRunType,
    graph: StateGraph,
    state: WorkflowState,
    context: ContextSchema,
    thread_id: str,
) -> WorkflowState:
    """
    Run a workflow using LangGraph, persisting the state to the database.

    Args:
        workflow_run_id: The ID of the workflow run record
        workflow_type: The type of the workflow
        graph: The LangGraph graph to run
        state: The initial state of the workflow
        context: The context of the workflow
        thread_id: The LangGraph thread ID used by the checkpointer

    Returns:
        The updated state of the workflow
    """
    project_id = context.project_id

    logger.info(
        f"Starting workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    # Mark as RUNNING
    await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.RUNNING)

    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer).with_config(
            {
                "run_name": f"{workflow_type.value}",
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_session_id": project_id},
                "max_concurrency": env_config.LANGGRAPH_MAX_CONCURRENCY,
            }
        )

        checkpoint_id = None
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

            # Get checkpoint ID for debugging after successful completion
            try:
                state_snapshot = await app.aget_state(
                    {"configurable": {"thread_id": thread_id}}
                )
                if state_snapshot and state_snapshot.config:
                    checkpoint_id = state_snapshot.config.get("configurable", {}).get(
                        "checkpoint_id"
                    )
            except Exception as e:
                logger.warning(f"Could not get checkpoint ID: {e}")
        except Exception as e:
            logger.error(f"Error streaming state: {e}", exc_info=True)
            updated_state.errors.append(
                WorkflowError(
                    task_name="global",
                    error=str(e),
                    workflow_run_id=workflow_run_id,
                )
            )
        finally:
            await update_workflow_run_status(
                workflow_run_id, WorkflowRunStatus.COMPLETED
            )

            # Persist issues after workflow completion
            await _persist_issues_from_state(
                workflow_run_id=workflow_run_id,
                project_id=project_id,
                workflow_type=workflow_type,
                state=updated_state,
                checkpoint_id=checkpoint_id,
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


async def _persist_issues_from_state(
    workflow_run_id: str,
    project_id: str | None,
    workflow_type: WorkflowRunType,
    state: WorkflowState,
    checkpoint_id: str | None,
) -> None:
    """
    Persist issues from workflow state to the database.

    Uses the workflow manifest to convert state to issues.
    Loads all existing workflow states for the project so manifests that
    depend on other workflow states (e.g. reference_validation reading
    reference_extraction) can resolve their data correctly.
    """
    if not project_id:
        logger.debug("No project_id, skipping issue persistence")
        return

    try:
        manifest = get_workflow_manifest(workflow_type, raise_exception=False)
        if manifest is None:
            logger.debug(f"No manifest for {workflow_type}, skipping issue persistence")
            return

        # Load all existing workflow states for the project so manifests
        # that read data from other workflow states can resolve correctly.
        from lib.services.workflow_runs import get_project_workflow_runs

        workflow_runs = await get_project_workflow_runs(
            project_id, include_internal=True
        )
        existing_states: list[WorkflowState] = [
            run.state for run in workflow_runs if run.state is not None
        ]

        # Convert state to issues using the manifest
        issues = manifest.convert_state_to_issues(state, existing_states)

        if not issues:
            logger.debug(f"No issues to persist for {workflow_type}")
            return

        await persist_workflow_issues(
            workflow_run_id=uuid.UUID(workflow_run_id),
            project_id=uuid.UUID(project_id),
            workflow_type=workflow_type,
            issues=issues,
            checkpoint_id=checkpoint_id,
        )
    except Exception as e:
        logger.error(f"Error persisting issues: {e}", exc_info=True)
