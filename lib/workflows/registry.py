from typing import Type, TypeVar

from fastapi import HTTPException
from langgraph.graph import StateGraph

from lib.config.env import config as env_config
from lib.services.file import FileDocument
from lib.services.vector_store import VectorStoreService
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    ClaimSubstantiatorStateSummary,
    SubstantiationWorkflowConfig,
)
from lib.workflows.methodological_alignment.graph import (
    build_methodological_alignment_graph,
)
from lib.workflows.methodological_alignment.state import (
    MethodologicalAlignmentState,
    MethodologicalAlignmentWorkflowConfig,
)
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.reference_downloader.graph import build_reference_downloader_graph
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
)

WorkflowState = (
    ClaimSubstantiatorState | MethodologicalAlignmentState | ReferenceDownloaderState
)

WorkflowStateType = TypeVar("WorkflowStateType", bound=BaseWorkflowState)


def create_graph(type: WorkflowRunType) -> StateGraph:
    match type:
        case WorkflowRunType.CLAIM_SUBSTANTIATION:
            return build_claim_substantiator_graph()
        case WorkflowRunType.METHODOLOGICAL_ALIGNMENT:
            return build_methodological_alignment_graph()
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return build_reference_downloader_graph()
        case _:
            raise ValueError(f"Unknown workflow type: {type}")


def get_config_type(type: WorkflowRunType) -> Type[BaseWorkflowConfig]:
    match type:
        case WorkflowRunType.CLAIM_SUBSTANTIATION:
            return SubstantiationWorkflowConfig
        case WorkflowRunType.METHODOLOGICAL_ALIGNMENT:
            return MethodologicalAlignmentWorkflowConfig
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return ReferenceDownloaderWorkflowConfig
        case _:
            raise ValueError(f"Unknown workflow type: {type}")


def get_state_type(
    type: WorkflowRunType, summary: bool = False
) -> Type[BaseWorkflowState]:
    match type:
        case WorkflowRunType.CLAIM_SUBSTANTIATION:
            return (
                ClaimSubstantiatorStateSummary if summary else ClaimSubstantiatorState
            )
        case WorkflowRunType.METHODOLOGICAL_ALIGNMENT:
            return MethodologicalAlignmentState
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return ReferenceDownloaderState
        case _:
            raise ValueError(f"Unknown workflow type: {type}")


def create_context(config: BaseWorkflowConfig) -> ContextSchema:
    openai_api_key = (
        config.openai_api_key
        or env_config.OPENAI_API_KEY
        or env_config.AZURE_OPENAI_API_KEY
    )

    if not openai_api_key:
        raise ValueError("No OpenAI API key found in config or environment variables")

    return ContextSchema(
        openai_api_key=openai_api_key,
        vector_store=VectorStoreService(env_config.DATABASE_URL, openai_api_key),
    )


async def create_state(config: BaseWorkflowConfig) -> WorkflowStateType:
    """
    Create initial state for a workflow from the config.
    """

    match config.type:
        case WorkflowRunType.CLAIM_SUBSTANTIATION:
            raise ValueError(
                f"Claim substantiation workflow should be temporarily started from its own specific endpoint"
            )
        case WorkflowRunType.METHODOLOGICAL_ALIGNMENT:
            file = await _get_file_from_project(config.project_id)
            return MethodologicalAlignmentState(file=file)
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return ReferenceDownloaderState(config=config)
        case _:
            raise ValueError(f"Unknown workflow type: {config.type}")


async def _get_file_from_project(project_id: str) -> FileDocument:
    """
    Get the file from the CLAIM_SUBSTANTIATION workflow run for the project.

    Args:
        project_id: The project ID to get the file from

    Returns:
        The FileDocument from the CLAIM_SUBSTANTIATION workflow

    Raises:
        HTTPException: If no CLAIM_SUBSTANTIATION workflow run exists for the project
    """

    from lib.services.workflow_runs import (
        get_project_workflow_run_by_type,
        get_workflow_run_state,
    )
    from lib.workflows.models import WorkflowRunType

    if not project_id:
        raise ValueError("project_id is required to get file from project")

    # Get the CLAIM_SUBSTANTIATION workflow run for this project
    claim_workflow_run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.CLAIM_SUBSTANTIATION
    )

    if claim_workflow_run is None:
        raise HTTPException(
            status_code=404,
            detail=f"No claim substantiation workflow found for project {project_id}. Please run claim substantiation workflow first.",
        )

    claim_state: ClaimSubstantiatorStateSummary = await get_workflow_run_state(
        claim_workflow_run.id
    )
    return claim_state.file
