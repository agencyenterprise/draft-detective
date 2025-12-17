"""
FastAPI dependencies for form data processing.
"""

import uuid
from typing import Optional
from fastapi import Form, HTTPException
from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig
from lib.workflows.models import WorkflowRunType


async def build_config_from_form(
    use_toulmin: bool = Form(default=False),
    use_rag: bool = Form(default=True),
    domain: Optional[str] = Form(default=None),
    target_audience: Optional[str] = Form(default=None),
    target_chunk_indices: Optional[str] = Form(default=None),
    agents_to_run: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    openai_api_key: Optional[str] = Form(default=None),
    publication_date: Optional[str] = Form(default=None),
    workflow_types: Optional[str] = Form(default=None),
) -> SubstantiationWorkflowConfig:
    """
    Build SubstantiationWorkflowConfig from individual form fields.

    Args:
        use_toulmin: Whether to use Toulmin claim extraction approach
        use_rag: Whether to use RAG for claim verification
        domain: Domain context for more accurate analysis
        target_audience: Target audience context for analysis
        target_chunk_indices: Comma-separated chunk indices to process (optional)
        agents_to_run: Comma-separated agent names to run (optional)
        session_id: Session ID for Langfuse tracing (optional)
        openai_api_key: OpenAI API key to use for this workflow execution (optional)
        publication_date: Publication date of the document in YYYY-MM-DD format (optional)
        web_search_consent: Whether the user has consented to web search (optional)
        workflow_types: Comma-separated workflow types to run (optional)

    Returns:
        Configured SubstantiationWorkflowConfig instance

    Raises:
        HTTPException: If target_chunk_indices contains invalid integers or workflow_types contains invalid values
    """
    # Parse optional list fields
    parsed_target_chunk_indices = None
    if target_chunk_indices:
        try:
            parsed_target_chunk_indices = [
                int(x.strip()) for x in target_chunk_indices.split(",")
            ]
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="target_chunk_indices must be comma-separated integers",
            )

    parsed_agents_to_run = None
    if agents_to_run:
        parsed_agents_to_run = [x.strip() for x in agents_to_run.split(",")]

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

    if not session_id:
        session_id = str(uuid.uuid4())

    return SubstantiationWorkflowConfig(
        use_toulmin=use_toulmin,
        use_rag=use_rag,
        domain=domain,
        target_audience=target_audience,
        target_chunk_indices=parsed_target_chunk_indices,
        agents_to_run=parsed_agents_to_run,
        session_id=session_id,
        openai_api_key=openai_api_key,
        publication_date=publication_date,
        workflow_types=parsed_workflow_types,
    )
