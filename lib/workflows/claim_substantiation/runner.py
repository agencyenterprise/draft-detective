# Convenience helpers
import argparse
import asyncio
import logging
import uuid
from typing import List, Optional

from lib.config.langfuse import langfuse_handler
from lib.models.workflow_run import WorkflowRunStatus
from lib.services.file import FileDocument
from lib.services.workflow_runs import (
    upsert_workflow_run,
)
from lib.workflows.claim_substantiation.checkpointer import get_checkpointer
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


async def run_claim_substantiator(
    file: FileDocument,
    supporting_files: Optional[List[FileDocument]] = None,
    config: SubstantiationWorkflowConfig = None,
) -> ClaimSubstantiatorState:
    """
    Claim substantiation runner using LangGraph approach.

    Supports both full document processing and selective chunk re-evaluation:
    - For full processing: leave config.target_chunk_indices and config.agents_to_run as None
    - For selective re-evaluation: provide config.target_chunk_indices and/or config.agents_to_run
    - For re-evaluation with existing results: provide existing_state to preserve previous results

    This is the single, authoritative entry point for claim substantiation.
    """

    if config is None:
        config = SubstantiationWorkflowConfig()

    state = ClaimSubstantiatorState(
        file=file,
        supporting_files=supporting_files,
        config=config,
    )

    return await _execute(state)


async def reevaluate_single_chunk(
    original_result: ClaimSubstantiatorState,
    chunk_index: int,
    agents_to_run: List[str],
    config_overrides: SubstantiationWorkflowConfig = None,
) -> ClaimSubstantiatorState:
    """
    Re-evaluate a single chunk using unified LangGraph approach.
    """
    logger.info(f"Re-evaluating chunk {chunk_index} with agents {agents_to_run}")

    chunks = original_result.chunks
    if chunk_index >= len(chunks):
        raise ValueError(
            f"Chunk index {chunk_index} out of range (max: {len(chunks)-1})"
        )

    # Create updated config with overrides
    config = original_result.config.model_copy()
    if config_overrides:
        # Update config with any provided overrides
        config = config.model_copy(
            update=config_overrides.model_dump(exclude_none=True)
        )

    # Always override target_chunk_indices and agents_to_run for this specific operation
    config.target_chunk_indices = [chunk_index]
    config.agents_to_run = agents_to_run
    config.session_id = config.session_id or original_result.session_id

    state = original_result.model_copy(
        update={
            "config": config,
            "errors": [
                error
                for error in original_result.errors
                if error.chunk_index != chunk_index
            ],
        }
    )

    return await _execute(state)


async def _execute(state: ClaimSubstantiatorState):
    """
    Execute the claim substantiation workflow.

    Note: If reusing a session_id from a previous run with a different graph structure,
    checkpoints may cause unexpected behavior. Use a fresh session_id after graph changes.
    """
    graph = build_claim_substantiator_graph(
        use_toulmin=state.config.use_toulmin,
        run_literature_review=state.config.run_literature_review,
        run_suggest_citations=state.config.run_suggest_citations,
        use_rag=state.config.use_rag,
        run_live_reports=state.config.run_live_reports,
        run_reference_validation=state.config.run_reference_validation,
    )

    # Generate a fresh session ID if not provided to avoid checkpoint conflicts
    if state.config.session_id is None:
        state.config.session_id = str(uuid.uuid4())
        logger.info("Generated new session ID: %s", state.config.session_id)

    async with get_checkpointer() as checkpointer:
        app = graph.compile(checkpointer=checkpointer).with_config(
            {
                "callbacks": [langfuse_handler],
                "metadata": {"langfuse_session_id": state.config.session_id},
            }
        )

        workflow_run_id = await upsert_workflow_run(
            session_id=state.config.session_id,
            status=WorkflowRunStatus.RUNNING,
            title=state.file.file_name,
        )

        state.workflow_run_id = workflow_run_id
        updated_state = state

        try:
            async for values in app.astream(
                state,
                {"configurable": {"thread_id": state.config.session_id}},
                stream_mode="values",
            ):
                updated_state = ClaimSubstantiatorState(**values)

                await upsert_workflow_run(
                    session_id=state.config.session_id,
                    status=WorkflowRunStatus.RUNNING,
                    title=(
                        updated_state.main_document_summary.title
                        if updated_state.main_document_summary
                        and updated_state.main_document_summary.title
                        else None
                    ),
                )
        except Exception as e:
            logger.error(f"Error streaming state: {e}", exc_info=True)
            updated_state.errors.append(WorkflowError(task_name="global", error=str(e)))
        finally:
            await upsert_workflow_run(
                session_id=state.config.session_id,
                status=WorkflowRunStatus.COMPLETED,
            )

    return updated_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "main_document_path",
        help="Path to the main document to analyze",
        nargs="?",
        default="./tests/data/cryptocurrency-and-blockchain-minimal/main_document.docx",
    )
    parser.add_argument(
        "supporting_documents",
        nargs="*",
        default=[
            "./tests/data/cryptocurrency-and-blockchain-minimal/ref1.pdf",
            "./tests/data/cryptocurrency-and-blockchain-minimal/ref2.pdf",
            "./tests/data/cryptocurrency-and-blockchain-minimal/ref3.pdf",
            "./tests/data/cryptocurrency-and-blockchain-minimal/ref4.pdf",
            "./tests/data/cryptocurrency-and-blockchain-minimal/ref5.pdf",
            "./tests/data/cryptocurrency-and-blockchain-minimal/ref6.pdf",
        ],
        help="Paths to supporting documents (optional)",
    )
    parser.add_argument(
        "-t",
        "--use-toulmin",
        action="store_true",
        default=True,
        help="Use Toulmin claim detector",
    )
    parser.add_argument(
        "-s",
        "--suggest-citations",
        action="store_true",
        default=False,
        help="Suggest citations",
    )
    parser.add_argument(
        "-l",
        "--literature-review",
        action="store_true",
        default=False,
        help="Run literature review",
    )
    parser.add_argument(
        "-r",
        "--live-reports",
        action="store_true",
        default=False,
        help="Run live reports",
    )
    parser.add_argument(
        "--session-id",
        help="Session ID for Langfuse tracing",
        default=str(uuid.uuid4()),
    )
    args = parser.parse_args()

    config = SubstantiationWorkflowConfig(
        use_toulmin=args.use_toulmin,
        run_suggest_citations=args.suggest_citations,
        run_literature_review=args.literature_review,
        run_live_reports=args.live_reports,
        session_id=args.session_id,
    )
    result_state = asyncio.run(
        run_claim_substantiator_from_paths(
            args.main_document_path, args.supporting_documents, config
        )
    )
    print("Result state:")
    print(result_state)
