"""
FastAPI dependencies for form data processing.
"""

from typing import Optional
from fastapi import Form, HTTPException
from api.models import AnalysisFormConfig
from lib.workflows.models import ClaimExtractionVersion, WorkflowRunType


async def build_config_from_form(
    domain: Optional[str] = Form(default=None),
    target_audience: Optional[str] = Form(default=None),
    openai_api_key: Optional[str] = Form(default=None),
    publication_date: Optional[str] = Form(default=None),
    workflow_types: Optional[str] = Form(default=None),
    claim_extraction_version: str = Form(default=ClaimExtractionVersion.V2.value),
) -> AnalysisFormConfig:
    """
    Build AnalysisFormConfig from individual form fields.

    Args:
        domain: Domain context for more accurate analysis
        target_audience: Target audience context for analysis
        openai_api_key: OpenAI API key to use for this workflow execution (optional)
        publication_date: Publication date of the document in YYYY-MM-DD format (optional)
        workflow_types: Comma-separated workflow types to run (optional)
        claim_extraction_version: Claim extraction version to use ("v1" or "v2")

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

    try:
        parsed_version = ClaimExtractionVersion(claim_extraction_version)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid claim_extraction_version: {claim_extraction_version}. Must be 'v1' or 'v2'.",
        )

    return AnalysisFormConfig(
        domain=domain,
        target_audience=target_audience,
        openai_api_key=openai_api_key,
        publication_date=publication_date,
        workflow_types=parsed_workflow_types,
        claim_extraction_version=parsed_version,
    )
