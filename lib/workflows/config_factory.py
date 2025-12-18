"""
Factory for creating workflow-specific configs from base config.
"""

from datetime import date

from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig
from lib.workflows.citation_suggester.state import CitationSuggesterWorkflowConfig
from lib.workflows.literature_review.state import LiteratureReviewWorkflowConfig
from lib.workflows.live_reports.state import LiveReportsWorkflowConfig
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_validation.state import ReferenceValidationWorkflowConfig
from lib.workflows.registry import get_config_type
from lib.workflows.types import WorkflowConfig


def create_workflow_config(
    workflow_type: WorkflowRunType,
    base_config: SubstantiationWorkflowConfig,
) -> WorkflowConfig:
    """
    Create a workflow-specific config from the base SubstantiationWorkflowConfig.

    Handles workflow-specific fields (e.g., LiteratureReviewWorkflowConfig needs publication_date).

    Args:
        workflow_type: The type of workflow to create config for
        base_config: The base config containing common fields

    Returns:
        A workflow-specific config instance

    Raises:
        ValueError: If required fields are missing for the workflow type
    """
    config_type = get_config_type(workflow_type)

    # Common fields to copy from base config
    common_fields = {
        "project_id": base_config.project_id,
        "openai_api_key": base_config.openai_api_key,
    }

    # Handle workflow-specific configs
    if workflow_type == WorkflowRunType.CLAIM_SUBSTANTIATION:
        return SubstantiationWorkflowConfig(
            **common_fields,
            use_toulmin=base_config.use_toulmin,
            use_rag=base_config.use_rag,
            domain=base_config.domain,
            target_audience=base_config.target_audience,
            target_chunk_indices=base_config.target_chunk_indices,
            agents_to_run=base_config.agents_to_run,
            session_id=base_config.session_id,
            publication_date=base_config.publication_date,
            workflow_types=base_config.workflow_types,
        )

    elif workflow_type == WorkflowRunType.CITATION_SUGGESTER:
        return CitationSuggesterWorkflowConfig(**common_fields)

    elif workflow_type == WorkflowRunType.REFERENCE_VALIDATION:
        return ReferenceValidationWorkflowConfig(**common_fields)

    elif workflow_type == WorkflowRunType.LITERATURE_REVIEW:
        if not base_config.publication_date:
            raise ValueError(
                "publication_date is required for LiteratureReview workflow. "
                "Please provide it in the base config."
            )
        # Parse publication_date string to date if needed
        pub_date = base_config.publication_date
        if isinstance(pub_date, str):
            pub_date = date.fromisoformat(pub_date)

        return LiteratureReviewWorkflowConfig(
            **common_fields,
            document_publication_date=pub_date,
        )

    elif workflow_type == WorkflowRunType.LIVE_REPORTS:
        if not base_config.publication_date:
            raise ValueError(
                "publication_date is required for LiveReports workflow. "
                "Please provide it in the base config."
            )
        # Parse publication_date string to date if needed
        pub_date = base_config.publication_date
        if isinstance(pub_date, str):
            pub_date = date.fromisoformat(pub_date)

        return LiveReportsWorkflowConfig(
            **common_fields,
            document_publication_date=pub_date,
            domain=base_config.domain,
            target_audience=base_config.target_audience,
        )

    else:
        # For other workflow types, try to create with just common fields
        # This handles MethodologicalAlignment and others that only need base fields
        try:
            return config_type(**common_fields)
        except Exception as e:
            raise ValueError(
                f"Failed to create config for workflow type {workflow_type}: {e}"
            )
