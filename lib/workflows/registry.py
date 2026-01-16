import logging
from typing import Dict, List, Type

from langgraph.graph import StateGraph

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


def get_workflow_manifest(
    type: WorkflowRunType, raise_exception: bool = True
) -> WorkflowManifest:
    """
    Get a workflow manifest by type.
    """

    if type not in _workflow_manifest_registry and raise_exception:
        raise ValueError(f"No workflow manifest registered for type: {type}")

    return _workflow_manifest_registry.get(type)


def register_all_workflow_manifests():
    from lib.workflows.citation_detection.manifest import CitationDetectionManifest
    from lib.workflows.citation_suggester.manifest import CitationSuggesterManifest
    from lib.workflows.claim_extraction.manifest import ClaimExtractionManifest
    from lib.workflows.claim_reference_validation.manifest import (
        ClaimReferenceValidationManifest,
    )
    from lib.workflows.document_processing.manifest import DocumentProcessingManifest
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
        ClaimReferenceValidationManifest(),
        CitationSuggesterManifest(),
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
