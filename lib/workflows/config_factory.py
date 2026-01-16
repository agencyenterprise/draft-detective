"""
Factory for creating workflow-specific configs from base config.
"""

from api.models import StartMultipleWorkflowsRequest
from lib.models.project import Project
from lib.workflows.citation_suggester.state import CitationSuggesterWorkflowConfig
from lib.workflows.literature_review.state import LiteratureReviewWorkflowConfig
from lib.workflows.live_reports.state import LiveReportsWorkflowConfig
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_validation.state import ReferenceValidationWorkflowConfig
from lib.workflows.registry import get_config_type
from lib.workflows.types import WorkflowConfig


def create_workflow_config(
    project: Project,
    workflow_type: WorkflowRunType,
    request: StartMultipleWorkflowsRequest,
) -> WorkflowConfig:
    """
    Create a workflow-specific config from the request.

    Handles workflow-specific fields (e.g., LiteratureReviewWorkflowConfig needs publication_date).

    Args:
        project: The project to create the config for
        workflow_type: The type of workflow to create config for
        request: The request containing project_id and optional openai_api_key

    Returns:
        A workflow-specific config instance

    Raises:
        ValueError: If required fields are missing for the workflow type
    """
    config_type = get_config_type(workflow_type)

    # Common fields to copy from request and project
    common_fields = {
        "project_id": request.project_id,
        "openai_api_key": request.openai_api_key,
        "domain": project.domain,
        "target_audience": project.target_audience,
        "publication_date": (
            project.publication_date.isoformat() if project.publication_date else None
        ),
    }

    # Handle workflow-specific configs
    if workflow_type == WorkflowRunType.CITATION_SUGGESTER:
        return CitationSuggesterWorkflowConfig(**common_fields)

    elif workflow_type == WorkflowRunType.REFERENCE_VALIDATION:
        return ReferenceValidationWorkflowConfig(**common_fields)

    elif workflow_type == WorkflowRunType.LITERATURE_REVIEW:
        return LiteratureReviewWorkflowConfig(**common_fields)

    elif workflow_type == WorkflowRunType.LIVE_REPORTS:
        return LiveReportsWorkflowConfig(**common_fields)

    else:
        # For other workflow types, try to create with just common fields
        # This handles MethodologicalAlignment and others that only need base fields
        try:
            return config_type(**common_fields)
        except Exception as e:
            raise ValueError(
                f"Failed to create config for workflow type {workflow_type}: {e}"
            )
