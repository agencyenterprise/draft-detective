import logging
from typing import Dict, List, Literal, Optional, Type, overload

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import BaseWorkflowConfig, WorkflowRunType
from lib.workflows.workflow_types import WorkflowConfig, WorkflowState

logger = logging.getLogger(__name__)


_workflow_manifest_registry: Dict[WorkflowRunType, WorkflowManifest] = {}


def get_all_manifests() -> Dict[WorkflowRunType, WorkflowManifest]:
    """Get all registered workflow manifests."""
    return dict(_workflow_manifest_registry)


def is_available_workflow_type(workflow_type: WorkflowRunType | str) -> bool:
    """Whether a persisted workflow type still has a manifest behind it.

    Rows outlive the workflows that wrote them: `workflow_runs.type` and
    `issues.workflow_type` keep whatever slug was current when they were
    written, and nothing rewrites them when a workflow is retired. Anything that
    loads such a row has to decide whether the workflow still exists before
    handing it to a client — without a manifest there is no state model to
    hydrate it with, no display name to label it, and nothing to re-run.

    Accepts the raw `str` these columns actually yield as well as the enum:
    `WorkflowRunType` is a `(str, Enum)`, so both hash and compare alike as dict
    keys. Retired types are exactly the ones that miss.
    """
    return workflow_type in _workflow_manifest_registry


def available_workflow_type_values() -> List[str]:
    """Slugs of every workflow type that still has a manifest.

    The collection form of `is_available_workflow_type`, for callers that filter
    in SQL rather than in Python.
    """
    return [workflow_type.value for workflow_type in _workflow_manifest_registry]


def register_workflow_manifest(manifest: WorkflowManifest) -> None:
    """
    Register a workflow manifest.
    """

    if manifest.type in _workflow_manifest_registry:
        raise ValueError(
            f"Workflow manifest already registered for type: {manifest.type}"
        )

    _workflow_manifest_registry[manifest.type] = manifest


@overload
def get_workflow_manifest(
    type: WorkflowRunType, raise_exception: Literal[True] = True
) -> WorkflowManifest: ...


@overload
def get_workflow_manifest(
    type: WorkflowRunType, raise_exception: Literal[False]
) -> Optional[WorkflowManifest]: ...


def get_workflow_manifest(
    type: WorkflowRunType, raise_exception: bool = True
) -> Optional[WorkflowManifest]:
    """
    Get a workflow manifest by type.
    """

    if type not in _workflow_manifest_registry and raise_exception:
        raise ValueError(f"No workflow manifest registered for type: {type}")

    return _workflow_manifest_registry.get(type)


def register_all_workflow_manifests():
    from lib.workflows.abbreviation_scan_v2.manifest import AbbreviationScanV2Manifest
    from lib.workflows.document_structure.manifest import DocumentStructureManifest
    from lib.workflows.figures_tables_check.manifest import FiguresTablesCheckManifest
    from lib.workflows.about_this_ger.manifest import AboutThisGerManifest
    from lib.workflows.advocacy_tone_v2.manifest import AdvocacyToneV2Manifest
    from lib.workflows.claim_reference_validation_v2.manifest import (
        ClaimReferenceValidationV2Manifest,
    )
    from lib.workflows.document_processing.manifest import DocumentProcessingManifest
    from lib.workflows.document_summarization.manifest import (
        DocumentSummarizationManifest,
    )
    from lib.workflows.inference_validation_v2.manifest import (
        InferenceValidationV2Manifest,
    )
    from lib.workflows.literature_review_v2.manifest import LiteratureReviewV2Manifest
    from lib.workflows.live_reports_v2.manifest import LiveReportsV2Manifest
    from lib.workflows.methodological_alignment.manifest import (
        MethodologicalAlignmentManifest,
    )
    from lib.workflows.reference_downloader.manifest import ReferenceDownloaderManifest
    from lib.workflows.reference_extraction.manifest import ReferenceExtractionManifest
    from lib.workflows.reference_file_matching.manifest import (
        ReferenceFileMatchingManifest,
    )
    from lib.workflows.recommendation_check.manifest import (
        RecommendationCheckManifest,
    )
    from lib.workflows.reference_validation_v2.manifest import (
        ReferenceValidationV2Manifest,
    )
    from lib.workflows.results_extraction.manifest import ResultsExtractionManifest
    from lib.workflows.reviewer_2.manifest import Reviewer2Manifest
    from lib.workflows.revision_planning_summary.manifest import (
        RevisionPlanningSummaryManifest,
    )
    from lib.workflows.reviewer_response_memos.manifest import (
        ReviewerResponseMemosManifest,
    )
    from lib.workflows.reviewer_coverage_report.manifest import (
        ReviewerCoverageReportManifest,
    )

    manifests = [
        DocumentProcessingManifest(),
        DocumentSummarizationManifest(),
        ReferenceExtractionManifest(),
        ReferenceFileMatchingManifest(),
        ClaimReferenceValidationV2Manifest(),
        AbbreviationScanV2Manifest(),
        InferenceValidationV2Manifest(),
        LiteratureReviewV2Manifest(),
        LiveReportsV2Manifest(),
        MethodologicalAlignmentManifest(),
        ReferenceDownloaderManifest(),
        ReferenceValidationV2Manifest(),
        ResultsExtractionManifest(),
        AdvocacyToneV2Manifest(),
        AboutThisGerManifest(),
        Reviewer2Manifest(),
        DocumentStructureManifest(),
        FiguresTablesCheckManifest(),
        RecommendationCheckManifest(),
        RevisionPlanningSummaryManifest(),
        ReviewerResponseMemosManifest(),
        ReviewerCoverageReportManifest(),
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


async def create_state(
    config: WorkflowConfig,
    revision: int,
    prior_self_state: WorkflowState | None = None,
) -> WorkflowState:
    """
    Create initial state for a workflow from the config.

    Loads all workflow states (including internal ones) to support dependency
    resolution. ``prior_self_state`` is the same-type prior run's state (or None);
    it is passed to create_initial_state, which most workflows ignore — only
    accumulating workflows (e.g. reference_downloader) seed from it.
    """
    from lib.services.workflow_runs import get_project_workflow_runs

    # Include internal workflows so dependencies can access their states
    workflow_runs = await get_project_workflow_runs(
        config.project_id, revision=revision, include_internal=True
    )
    existing_states: List[WorkflowState] = [
        run.state for run in workflow_runs if run.state is not None
    ]
    manifest = get_workflow_manifest(config.type)
    return await manifest.create_initial_state(
        config, existing_states, revision, prior_self_state=prior_self_state
    )
