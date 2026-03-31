"""
FastAPI dependencies for form data processing.
"""

from typing import Optional
from fastapi import Form, HTTPException
from lib.api.models import AnalysisFormConfig
from lib.workflows.models import WorkflowRunType


async def build_config_from_form(
    domain: Optional[str] = Form(default=None),
    target_audience: Optional[str] = Form(default=None),
    openai_api_key: Optional[str] = Form(default=None),
    publication_date: Optional[str] = Form(default=None),
    workflow_types: Optional[str] = Form(default=None),
) -> AnalysisFormConfig:
    """
    Build AnalysisFormConfig from individual form fields.

    Args:
        domain: Domain context for more accurate analysis
        target_audience: Target audience context for analysis
        openai_api_key: OpenAI API key to use for this workflow execution (optional)
        publication_date: Publication date of the document in YYYY-MM-DD format (optional)
        workflow_types: Comma-separated workflow types to run (optional)

    Returns:
        Configured AnalysisFormConfig instance

    Raises:
        HTTPException: If workflow_types contains invalid values
    """
    parsed_workflow_types = None
    if workflow_types:
        try:
            parsed_workflow_types = [
                WorkflowRunType(x.strip()) for x in workflow_types.split(",")
            ]
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid workflow type in workflow_types: {str(e)}",
            )

    return AnalysisFormConfig(
        domain=domain,
        target_audience=target_audience,
        openai_api_key=openai_api_key,
        publication_date=publication_date,
        workflow_types=parsed_workflow_types,
    )
