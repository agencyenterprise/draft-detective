"""
FastAPI dependencies for form data processing.
"""

import uuid
from typing import Optional, List
from fastapi import Form, HTTPException
from datetime import datetime
from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig


async def build_config_from_form(
    use_toulmin: bool = Form(
        default=True
    ),  # (2025-11-07) TODO: Leaving this as True for now. Once we change the frontend we can set this to False.
    run_literature_review: bool = Form(default=True),
    run_suggest_citations: bool = Form(default=True),
    use_rag: bool = Form(default=True),
    run_live_reports: bool = Form(default=False),
    run_reference_validation: bool = Form(default=False),
    domain: Optional[str] = Form(default=None),
    target_audience: Optional[str] = Form(default=None),
    target_chunk_indices: Optional[str] = Form(default=None),
    document_publication_date: Optional[str] = Form(default=None),
    agents_to_run: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
) -> SubstantiationWorkflowConfig:
    """
    Build SubstantiationWorkflowConfig from individual form fields.

    Args:
        use_toulmin: Whether to use Toulmin claim extraction approach
        run_literature_review: Whether to run the literature review
        run_suggest_citations: Whether to run the citation suggestions
        use_rag: Whether to use RAG for claim verification
        run_live_reports: Whether to run the live reports analysis
        run_reference_validation: Whether to validate references using web search
        domain: Domain context for more accurate analysis
        target_audience: Target audience context for analysis
        target_chunk_indices: Comma-separated chunk indices to process (optional)
        document_publication_date: Publication date of the document (optional)
        agents_to_run: Comma-separated agent names to run (optional)
        session_id: Session ID for Langfuse tracing (optional)

    Returns:
        Configured SubstantiationWorkflowConfig instance

    Raises:
        HTTPException: If target_chunk_indices contains invalid integers
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

    if not session_id:
        session_id = str(uuid.uuid4())

    # Parse publication date
    parsed_publication_date = None
    if document_publication_date:
        try:
            parsed_publication_date = datetime.strptime(
                document_publication_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            raise HTTPException(
                status_code=422, detail="document_publication_date must be YYYY-MM-DD"
            )

    return SubstantiationWorkflowConfig(
        use_toulmin=use_toulmin,
        run_literature_review=run_literature_review,
        run_suggest_citations=run_suggest_citations,
        use_rag=use_rag,
        run_live_reports=run_live_reports,
        run_reference_validation=run_reference_validation,
        domain=domain,
        target_audience=target_audience,
        target_chunk_indices=parsed_target_chunk_indices,
        document_publication_date=parsed_publication_date,
        agents_to_run=parsed_agents_to_run,
        session_id=session_id,
    )
