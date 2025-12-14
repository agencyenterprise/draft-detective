import logging
from typing import Type, TypeVar

from fastapi import HTTPException
from langgraph.graph import StateGraph

from lib.config.env import config as env_config
from lib.models.user import User
from lib.services.vector_store import VectorStoreService
from lib.workflows.citation_suggester.graph import build_citation_suggester_graph
from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.context import ContextSchema
from lib.workflows.docx_generation.graph import build_docx_generation_graph
from lib.workflows.docx_generation.state import (
    DocxGenerationState,
    DocxGenerationWorkflowConfig,
)
from lib.workflows.literature_review.graph import build_literature_review_graph
from lib.workflows.literature_review.state import (
    LiteratureReviewState,
    LiteratureReviewWorkflowConfig,
)
from lib.workflows.live_reports.graph import build_live_reports_graph
from lib.workflows.live_reports.state import LiveReportsState, LiveReportsWorkflowConfig
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
from lib.workflows.reference_validation.graph import build_reference_validation_graph
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationWorkflowConfig,
)

logger = logging.getLogger(__name__)

WorkflowState = (
    ClaimSubstantiatorState
    | MethodologicalAlignmentState
    | ReferenceDownloaderState
    | DocxGenerationState
    | LiteratureReviewState
    | LiveReportsState
    | ReferenceValidationState
    | CitationSuggesterState
)

WorkflowConfig = (
    SubstantiationWorkflowConfig
    | MethodologicalAlignmentWorkflowConfig
    | ReferenceDownloaderWorkflowConfig
    | LiteratureReviewWorkflowConfig
    | LiveReportsWorkflowConfig
    | ReferenceValidationWorkflowConfig
    | CitationSuggesterWorkflowConfig
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
        case WorkflowRunType.DOCX_GENERATION:
            return build_docx_generation_graph()
        case WorkflowRunType.LITERATURE_REVIEW:
            return build_literature_review_graph()
        case WorkflowRunType.LIVE_REPORTS:
            return build_live_reports_graph()
        case WorkflowRunType.REFERENCE_VALIDATION:
            return build_reference_validation_graph()
        case WorkflowRunType.CITATION_SUGGESTER:
            return build_citation_suggester_graph()
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
        case WorkflowRunType.DOCX_GENERATION:
            return DocxGenerationWorkflowConfig
        case WorkflowRunType.LITERATURE_REVIEW:
            return LiteratureReviewWorkflowConfig
        case WorkflowRunType.LIVE_REPORTS:
            return LiveReportsWorkflowConfig
        case WorkflowRunType.REFERENCE_VALIDATION:
            return ReferenceValidationWorkflowConfig
        case WorkflowRunType.CITATION_SUGGESTER:
            return CitationSuggesterWorkflowConfig
        case _:
            raise ValueError(f"Unknown workflow type: {type}")


def get_state_type(type: WorkflowRunType) -> Type[BaseWorkflowState]:
    match type:
        case WorkflowRunType.CLAIM_SUBSTANTIATION:
            return ClaimSubstantiatorState
        case WorkflowRunType.METHODOLOGICAL_ALIGNMENT:
            return MethodologicalAlignmentState
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return ReferenceDownloaderState
        case WorkflowRunType.DOCX_GENERATION:
            return DocxGenerationState
        case WorkflowRunType.LITERATURE_REVIEW:
            return LiteratureReviewState
        case WorkflowRunType.LIVE_REPORTS:
            return LiveReportsState
        case WorkflowRunType.REFERENCE_VALIDATION:
            return ReferenceValidationState
        case WorkflowRunType.CITATION_SUGGESTER:
            return CitationSuggesterState
        case _:
            raise ValueError(f"Unknown workflow type: {type}")


def create_context(
    config: BaseWorkflowConfig,
    workflow_run_id: str | None = None,
    user: User | None = None,
) -> ContextSchema:
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
        user_id=str(user.id) if user else None,
        project_id=config.project_id,
        workflow_run_id=workflow_run_id,
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
            claim_state = await _get_claim_state_from_project(config.project_id)
            return MethodologicalAlignmentState(file=claim_state.file)
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return ReferenceDownloaderState(config=config)
        case WorkflowRunType.DOCX_GENERATION:
            return DocxGenerationState(config=config)
        case WorkflowRunType.LITERATURE_REVIEW:
            claim_state = await _get_claim_state_from_project(config.project_id)
            return LiteratureReviewState(
                config=config,
                file=claim_state.file,
                references=claim_state.references,
            )
        case WorkflowRunType.LIVE_REPORTS:
            claim_state = await _get_claim_state_from_project(config.project_id)
            # Carry over optional context from the claim workflow if not provided
            if config.domain is None:
                config.domain = claim_state.config.domain
            if config.target_audience is None:
                config.target_audience = claim_state.config.target_audience

            return LiveReportsState(
                config=config,
                file=claim_state.file,
                references=claim_state.references,
                chunks=claim_state.chunks,
                main_document_summary=claim_state.main_document_summary,
            )
        case WorkflowRunType.REFERENCE_VALIDATION:
            claim_state = await _get_claim_state_from_project(config.project_id)
            return ReferenceValidationState(
                config=config,
                references=claim_state.references,
            )
        case WorkflowRunType.CITATION_SUGGESTER:
            # Get full claim state (not summary) to access full chunks with claims, citations, etc.
            claim_workflow_state = await _get_claim_state_from_project(
                config.project_id
            )
            # Get literature review if available (optional)
            literature_review_state = await _get_literature_review_state_from_project(
                config.project_id
            )

            return CitationSuggesterState(
                config=config,
                file=claim_workflow_state.file,
                references=claim_workflow_state.references,
                chunks=claim_workflow_state.chunks,
                supporting_files=claim_workflow_state.supporting_files,
                supporting_documents_summaries=claim_workflow_state.supporting_documents_summaries,
                literature_review=(
                    literature_review_state.literature_review
                    if literature_review_state
                    else None
                ),
            )
        case _:
            raise ValueError(f"Unknown workflow type: {config.type}")


async def _get_claim_state_from_project(
    project_id: str,
) -> ClaimSubstantiatorState:
    """
    Get the full claim substantiation state from the CLAIM_SUBSTANTIATION workflow run for the project.

    Args:
        project_id: The project ID to get the state from

    Returns:
        The full ClaimSubstantiatorState from the CLAIM_SUBSTANTIATION workflow

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

    claim_state: ClaimSubstantiatorState = await get_workflow_run_state(
        claim_workflow_run.id
    )
    return claim_state


async def _get_literature_review_state_from_project(
    project_id: str,
) -> LiteratureReviewState | None:
    """
    Get the literature review state from the LITERATURE_REVIEW workflow run for the project.
    """
    from lib.services.workflow_runs import (
        get_project_workflow_run_by_type,
        get_workflow_run_state,
    )
    from lib.workflows.models import WorkflowRunType

    literature_review_run = await get_project_workflow_run_by_type(
        project_id, WorkflowRunType.LITERATURE_REVIEW
    )

    if literature_review_run is None:
        return None

    literature_review_state = await get_workflow_run_state(literature_review_run.id)
    return literature_review_state
