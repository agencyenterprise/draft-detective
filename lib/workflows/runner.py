import asyncio
import logging
import uuid

from langfuse import propagate_attributes
from langgraph.graph import StateGraph

from lib.services.workflow_orchestration import wait_for_dependencies
from lib.config.env import config as env_config
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback
from lib.config.llm_models import LLMModel
from lib.models.user import User
from lib.models.workflow_run import (
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.issue_persistence import persist_workflow_issues
from lib.services.users import get_user_decrypted_api_key
from lib.services.vector_store import VectorStoreService
from lib.services.workflow_runs import (
    fail_workflow_run,
    get_latest_workflow_run_state_by_type,
    persist_workflow_run_state,
    update_workflow_run_status,
)
from lib.workflows.context import ContextSchema
from lib.workflows.error_details import build_workflow_error
from lib.workflows.models import (
    BaseWorkflowConfig,
    DependencyWaitTimeoutError,
    WorkflowCancelledError,
)
from lib.workflows.registry import create_graph, create_state, get_workflow_manifest
from lib.workflows.workflow_types import WorkflowConfig, WorkflowState

logger = logging.getLogger(__name__)


async def run_workflow_with_dependency_check(
    config: WorkflowConfig,
    thread_id: str,
    workflow_run_id: str,
    user: User,
    revision: int,
    seed_prior_state: bool = True,
) -> None:
    """
    Run a workflow after checking and waiting for its dependencies to complete.

    This function:
    1. Waits for any same-type workflow and dependencies to complete
    2. Executes the workflow

    Args:
        config: The workflow config to run
        thread_id: The run's opaque LangGraph thread id (stored on the run record)
        workflow_run_id: The unique ID of this workflow run (for same-type locking)
        user: The user running the workflow
        revision: The project revision this workflow run belongs to
        seed_prior_state: When True (fresh runs), accumulating workflows seed
            their initial state from the prior same-type run. Set False when
            resuming — a resumed run continues its own state and must not adopt
            another run's. The prior state is read downstream, after the wait.
    """

    try:
        # Wait for same-type lock and dependencies to complete
        await wait_for_dependencies(
            config.type, config.project_id, workflow_run_id, revision=revision
        )

        # Run the workflow
        await run_workflow_from_config(
            config=config,
            thread_id=thread_id,
            workflow_run_id=workflow_run_id,
            user=user,
            revision=revision,
            seed_prior_state=seed_prior_state,
        )

    except WorkflowCancelledError:
        logger.info(f"Workflow {workflow_run_id} ({config.type.value}) was cancelled")
        # Status is already CANCELLED in DB; the guard in update_workflow_run_status
        # prevents it from being overwritten

    except DependencyWaitTimeoutError as e:
        logger.error(
            f"Workflow {workflow_run_id} ({config.type.value}) timed out waiting "
            f"for dependencies: {e}"
        )
        await fail_workflow_run(
            workflow_run_id,
            config.project_id,
            failure_reason=WorkflowRunFailureReason.DEPENDENCY_TIMEOUT,
            failure_message=str(e),
        )

    except Exception as e:
        # Errors that escape run_workflow's own handler land here. run_workflow
        # already marks itself FAILED in that case; this branch covers errors
        # raised before/after run_workflow runs (e.g. setup failures).
        logger.error(f"Error running workflow: {e}", exc_info=True)
        await fail_workflow_run(
            workflow_run_id,
            config.project_id,
            failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
            failure_message=str(e),
        )


async def run_workflow_from_config(
    config: WorkflowConfig,
    thread_id: str,
    workflow_run_id: str,
    user: User,
    revision: int,
    seed_prior_state: bool = True,
) -> WorkflowState:
    graph = create_graph(config.type)
    context = create_context(
        config, workflow_run_id=workflow_run_id, user=user, revision=revision
    )

    # Redact the OpenAI API key from the config so it doesn't get saved in the state
    config.openai_api_key = "[REDACTED]"

    # Read the prior same-type run's state here — at execution time, after the
    # same-type wait in run_workflow_with_dependency_check has resolved — so
    # accumulating workflows seed from the prior run's FINAL state rather than a
    # snapshot taken while it was still running. Exclude this run (its state_json
    # is still NULL now anyway). Skipped on resume (seed_prior_state=False).
    prior_self_state = (
        await get_latest_workflow_run_state_by_type(
            config.project_id, config.type, revision, exclude_run_id=workflow_run_id
        )
        if seed_prior_state
        else None
    )

    state = await create_state(
        config, revision=revision, prior_self_state=prior_self_state
    )

    with propagate_attributes(user_id=context.user_id):
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
        thread_id: The run's opaque LangGraph thread id (stored on the run record)

    Returns:
        The updated state of the workflow
    """
    project_id = context.project_id

    logger.info(
        f"Starting workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    # Mark as RUNNING
    await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.RUNNING)

    error_logging_callback = ErrorLoggingCallback(
        workflow_run_id=workflow_run_id,
        project_id=project_id,
    )

    manifest = get_workflow_manifest(workflow_type, raise_exception=False)
    max_duration = manifest.max_duration_seconds if manifest else 1 * 60 * 60

    # Workflows that fan out heavy per-item LLM calls can pin a lower
    # concurrency than the global default to stay under provider rate limits.
    max_concurrency = (
        manifest.max_concurrency if manifest else env_config.LANGGRAPH_MAX_CONCURRENCY
    )

    app = graph.compile().with_config(
        {
            "run_name": f"{workflow_type.value}",
            "callbacks": [langfuse_handler, error_logging_callback],
            "metadata": {"langfuse_session_id": project_id},
            "max_concurrency": max_concurrency,
        }
    )

    updated_state = state.model_copy(deep=True, update={"errors": []})

    try:
        async with asyncio.timeout(max_duration):
            async for values in app.astream(  # type: ignore[call-overload]
                updated_state,
                stream_mode="values",
                context=context,
            ):
                updated_state = updated_state.model_copy(update=values)
                # state_json is the single source of truth: snapshot the
                # accumulated state after every node yield.
                await persist_workflow_run_state(workflow_run_id, updated_state)

        # Persist issues after workflow completion. Per-node errors collected
        # in updated_state.errors stay surfaced through state — the run still
        # transitions to COMPLETED ("completed with errors") below.
        await _persist_issues_from_state(
            workflow_run_id=workflow_run_id,
            project_id=project_id,
            workflow_type=workflow_type,
            state=updated_state,
            # The LangGraph checkpointer is retired; no checkpoint id to record.
            checkpoint_id=None,
            revision=context.revision,
        )

        await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.COMPLETED)

    except WorkflowCancelledError:
        logger.info(
            f"Workflow {workflow_type} for project {project_id} was cancelled — running cleanup"
        )
        if manifest:
            updated_state = await manifest.on_cancel(updated_state)
            await persist_workflow_run_state(workflow_run_id, updated_state)
        # Status is already CANCELLED in DB; CANCELLED-guard in
        # update_workflow_run_status keeps it that way.

    except asyncio.TimeoutError:
        logger.error(
            f"Workflow {workflow_type} for project {project_id} exceeded "
            f"max_duration={max_duration}s — marking FAILED"
        )
        if manifest:
            # on_cancel is the right place for abnormal-teardown cleanup
            # (per-item statuses stuck in 'pending' would remain otherwise).
            updated_state = await manifest.on_cancel(updated_state)
            await persist_workflow_run_state(workflow_run_id, updated_state)
        await fail_workflow_run(
            workflow_run_id,
            project_id,
            failure_reason=WorkflowRunFailureReason.TIMEOUT,
            failure_message=f"Exceeded max_duration of {max_duration}s",
        )

    except Exception as e:
        logger.error(f"Error running workflow {workflow_type}: {e}", exc_info=True)
        error = build_workflow_error(
            task_name="global",
            exc=e,
            workflow_run_id=workflow_run_id,
        )

        # Persist the error onto state_json so the reader path surfaces it in
        # the workflow state for debugging.
        updated_state = updated_state.model_copy(
            update={"errors": [*updated_state.errors, error]}
        )
        await persist_workflow_run_state(workflow_run_id, updated_state)
        await fail_workflow_run(
            workflow_run_id,
            project_id,
            failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
            failure_message=str(e),
        )

    logger.info(
        f"Completed workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    return updated_state


def create_context(
    config: BaseWorkflowConfig,
    revision: int,
    workflow_run_id: str | None = None,
    user: User | None = None,
) -> ContextSchema:
    """
    Create workflow context.

    Key resolution: per-request key > user's stored key > server env var.
    Each workflow declares whether it requires an API key via requires_api_key().
    Workflows that don't use LLMs (data manipulation only) can return False.
    """
    user_stored_key = get_user_decrypted_api_key(user) if user else None
    openai_api_key = (
        config.openai_api_key or user_stored_key or env_config.OPENAI_API_KEY
    )

    if not openai_api_key and config.requires_api_key():
        raise ValueError("No OpenAI API key found in config or environment variables")

    # Only initialize vector store if we have an API key (needed for embeddings)
    vector_store = VectorStoreService(openai_api_key) if openai_api_key else None

    file_artifacts_service = FileArtifactsService(config.project_id, revision=revision)

    return ContextSchema(
        openai_api_key=openai_api_key,
        vector_store=vector_store,
        user_id=str(user.id) if user else None,
        project_id=config.project_id,
        workflow_run_id=workflow_run_id,
        file_artifacts_service=file_artifacts_service,
        revision=revision,
        model_override=LLMModel.from_model_name(config.model) if config.model else None,
    )


async def _persist_issues_from_state(
    workflow_run_id: str,
    project_id: str,
    workflow_type: WorkflowRunType,
    state: WorkflowState,
    checkpoint_id: str | None,
    revision: int = 1,
) -> None:
    """
    Persist issues from workflow state to the database.

    Uses the workflow manifest to convert state to issues.
    Loads all existing workflow states for the project so manifests that
    depend on other workflow states (e.g. reference_validation reading
    reference_extraction) can resolve their data correctly.
    """
    manifest = get_workflow_manifest(workflow_type, raise_exception=False)
    if manifest is None:
        logger.debug(f"No manifest for {workflow_type}, skipping issue persistence")
        return

    # Load all existing workflow states for the project and revision so manifests
    # that read data from other workflow states can resolve correctly.
    from lib.services.workflow_runs import get_project_workflow_runs

    workflow_runs = await get_project_workflow_runs(
        project_id, revision=revision, include_internal=True
    )
    existing_states: list[WorkflowState] = [
        run.state for run in workflow_runs if run.state is not None
    ]

    # Convert state to issues using the manifest
    issues = manifest.convert_state_to_issues(state, existing_states)

    await persist_workflow_issues(
        workflow_run_id=uuid.UUID(workflow_run_id),
        project_id=uuid.UUID(project_id),
        workflow_type=workflow_type,
        issues=issues,
        checkpoint_id=checkpoint_id,
        revision=revision,
    )
