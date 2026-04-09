"""
Factory for creating workflow-specific configs from base config.
"""

from lib.models.project import Project
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_config_type
from lib.workflows.workflow_types import WorkflowConfig


def create_workflow_config(
    project: Project,
    workflow_type: WorkflowRunType,
    openai_api_key: str | None = None,
) -> WorkflowConfig:
    """
    Create a workflow-specific config from the given parameters.

    Handles workflow-specific fields (e.g., LiteratureReviewWorkflowConfig needs publication_date).

    Args:
        project: The project to create the config for
        workflow_type: The type of workflow to create config for
        openai_api_key: Optional API key override

    Returns:
        A workflow-specific config instance

    Raises:
        ValueError: If required fields are missing for the workflow type
    """
    config_type = get_config_type(workflow_type)

    common_fields = {
        "type": workflow_type,
        "project_id": str(project.id),
        "openai_api_key": openai_api_key,
        "domain": project.domain,
        "target_audience": project.target_audience,
        "publication_date": (
            project.publication_date.isoformat() if project.publication_date else None
        ),
        "revision": project.current_revision,
    }

    try:
        return config_type.model_validate(common_fields)  # type: ignore
    except Exception as e:
        raise ValueError(
            f"Failed to create config for workflow type {workflow_type}: {e}"
        )
