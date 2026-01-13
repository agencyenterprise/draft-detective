import logging
from typing import Dict, List, Type

from langgraph.graph import StateGraph

from lib.config.env import config as env_config
from lib.models.user import User
from lib.services.vector_store import VectorStoreService
from lib.workflows.context import ContextSchema
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType
from lib.workflows.types import WorkflowState

logger = logging.getLogger(__name__)


_workflow_manifest_registry: Dict[WorkflowRunType, WorkflowManifest] = {}


def register_workflow_manifest(manifest: WorkflowManifest) -> None:
    """
    Register a workflow manifest.
    """

    if manifest.type in _workflow_manifest_registry:
        raise ValueError(
            f"Workflow manifest already registered for type: {manifest.type}"
        )

    _workflow_manifest_registry[manifest.type] = manifest


def get_workflow_manifest(type: WorkflowRunType) -> WorkflowManifest:
    """
    Get a workflow manifest by type.
    """

    if type not in _workflow_manifest_registry:
        raise ValueError(f"No workflow manifest registered for type: {type}")

    return _workflow_manifest_registry[type]


def register_all_workflow_manifests():
    from lib.workflows.citation_detection.manifest import CitationDetectionManifest
    from lib.workflows.citation_suggester.manifest import CitationSuggesterManifest
    from lib.workflows.claim_extraction.manifest import ClaimExtractionManifest
    from lib.workflows.claim_reference_validation.manifest import (
        ClaimReferenceValidationManifest,
    )
    from lib.workflows.claim_substantiation.manifest import ClaimSubstantiationManifest
    from lib.workflows.document_processing.manifest import DocumentProcessingManifest
    from lib.workflows.docx_generation.manifest import DocxGenerationManifest
    from lib.workflows.footnote_extraction.manifest import FootnoteExtractionManifest
    from lib.workflows.inference_validation.manifest import InferenceValidationManifest
    from lib.workflows.literature_review.manifest import LiteratureReviewManifest
    from lib.workflows.live_reports.manifest import LiveReportsManifest
    from lib.workflows.methodological_alignment.manifest import (
        MethodologicalAlignmentManifest,
    )
    from lib.workflows.reference_downloader.manifest import ReferenceDownloaderManifest
    from lib.workflows.reference_extraction.manifest import ReferenceExtractionManifest
    from lib.workflows.reference_validation.manifest import ReferenceValidationManifest
    from lib.workflows.results_extraction.manifest import ResultsExtractionManifest

    manifests = [
        DocumentProcessingManifest(),
        ReferenceExtractionManifest(),
        FootnoteExtractionManifest(),
        ClaimExtractionManifest(),
        CitationDetectionManifest(),
        ClaimSubstantiationManifest(),
        ClaimReferenceValidationManifest(),
        CitationSuggesterManifest(),
        DocxGenerationManifest(),
        InferenceValidationManifest(),
        LiteratureReviewManifest(),
        LiveReportsManifest(),
        MethodologicalAlignmentManifest(),
        ReferenceDownloaderManifest(),
        ReferenceValidationManifest(),
        ResultsExtractionManifest(),
    ]

    for manifest in manifests:
        register_workflow_manifest(manifest)


register_all_workflow_manifests()


def create_graph(type: WorkflowRunType) -> StateGraph:
    manifest = get_workflow_manifest(type)
    return manifest.build_graph()


def get_config_type(type: WorkflowRunType) -> Type[BaseWorkflowConfig]:
    manifest = get_workflow_manifest(type)
    return manifest.get_config_type()


def get_state_type(type: WorkflowRunType) -> Type[BaseWorkflowState]:
    manifest = get_workflow_manifest(type)
    return manifest.get_state_type()


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

    return ContextSchema(
        openai_api_key=openai_api_key,
        vector_store=vector_store,
        user_id=str(user.id) if user else None,
        project_id=config.project_id,
        workflow_run_id=workflow_run_id,
    )


async def create_state(config: BaseWorkflowConfig) -> WorkflowState:
    """
    Create initial state for a workflow from the config.

    Loads all workflow states (including internal ones) to support dependency resolution.
    """
    from lib.services.workflow_runs import get_project_workflow_runs

    # Include internal workflows so dependencies can access their states
    workflow_runs = await get_project_workflow_runs(
        config.project_id, include_internal=True
    )
    existing_states: List[WorkflowState] = [
        run.state for run in workflow_runs if run.state is not None
    ]
    manifest = get_workflow_manifest(config.type)
    return await manifest.create_initial_state(config, existing_states)
