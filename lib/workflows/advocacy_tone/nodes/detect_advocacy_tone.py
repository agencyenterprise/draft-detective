"""
Advocacy and Tone Detection Node.

Two-tier detection:
1. Procedural: Fast regex + TextBlob on ALL chunks
2. LLM: Verification ONLY for flagged chunks
"""

import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.advocacy_tone_verifier import AdvocacyToneVerifierAgent
from lib.run_utils import run_tasks
from lib.workflows.advocacy_tone.constants import CONTEXT_K
from lib.workflows.advocacy_tone.procedural import (
    build_context,
    detect_flags,
    has_any_flag,
    should_skip_chunk,
)
from lib.workflows.advocacy_tone.state import (
    AdvocacyToneCheckType,
    AdvocacyToneState,
    ChunkAdvocacyToneResult,
    LLMVerificationResult,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Detect advocacy and tone issues",
    "Detect trigger words, advocacy language, and subjective tone in document chunks",
)
async def detect_advocacy_tone(
    state: AdvocacyToneState, runtime: Runtime[ContextSchema]
):
    """Main detection node: procedural checks → LLM verification for flagged chunks."""
    chunks = await runtime.context.file_artifacts_service.get_chunks()
    agent = AdvocacyToneVerifierAgent(runtime.context)

    # Step 1: Procedural detection on all chunks
    results, flagged = _run_procedural_checks(chunks)
    logger.info(
        f"[AdvocacyTone] {len(results)} chunks analyzed, {len(flagged)} flagged"
    )

    if not flagged:
        return {"results": results}

    # Step 2: LLM verification for flagged chunks
    errors = await _run_llm_verification(
        flagged, chunks, agent, runtime.context.workflow_run_id
    )
    logger.info(f"[AdvocacyTone] LLM verification complete")

    return {"results": results, "errors": errors}


def _run_procedural_checks(chunks):
    """Run procedural checks, return (all_results, flagged_for_llm)."""
    results = []
    flagged = []

    for chunk in chunks:
        if should_skip_chunk(chunk):
            continue

        flags = detect_flags(chunk.content)
        result = ChunkAdvocacyToneResult(
            chunk_index=chunk.chunk_index, procedural_flags=flags
        )
        results.append(result)

        if has_any_flag(flags):
            flagged.append((chunk, result))

    return results, flagged


async def _run_llm_verification(flagged, chunks, agent, workflow_run_id: str | None):
    """Run LLM verification for flagged chunks."""
    tasks, metadata = _build_verification_tasks(flagged, chunks, agent)

    llm_results, exceptions = await run_tasks(tasks, desc="Verifying advocacy/tone")

    errors = []
    for i, (llm_result, exc) in enumerate(zip(llm_results, exceptions)):
        result_obj, check_type, chunk_idx = metadata[i]

        if exc:
            errors.append(
                WorkflowError(
                    task_name=f"verify_{check_type}",
                    error=str(exc),
                    chunk_index=chunk_idx,
                    workflow_run_id=workflow_run_id,
                )
            )
            continue

        if llm_result:
            _apply_llm_result(result_obj, check_type, llm_result)

    return errors


def _build_verification_tasks(flagged, chunks, agent):
    """Build LLM verification tasks for each flagged check type."""
    tasks, metadata = [], []

    for chunk, result in flagged:
        context = build_context(chunks, chunk, CONTEXT_K)
        flags = result.procedural_flags

        for check_type, is_flagged in [
            (AdvocacyToneCheckType.TRIGGER_WORDS, flags.trigger_words),
            (AdvocacyToneCheckType.ADVOCACY_LANGUAGE, flags.advocacy_language),
            (AdvocacyToneCheckType.SUBJECTIVE_TONE, flags.subjective_tone),
        ]:
            if is_flagged:
                tasks.append(
                    agent.ainvoke(
                        {
                            "check_type": check_type,
                            "target_sentence": chunk.content,
                            "context": context,
                        }
                    )
                )
                metadata.append((result, check_type.value, chunk.chunk_index))

    return tasks, metadata


def _apply_llm_result(result_obj, check_type, llm_result):
    """Apply LLM verification result to the chunk result."""
    verification = LLMVerificationResult(
        confirmed=llm_result.confirmed,
        explanation=llm_result.explanation,
        word_positions=llm_result.word_positions,
    )

    if check_type == "trigger_words":
        result_obj.llm_trigger_words = verification
    elif check_type == "advocacy_language":
        result_obj.llm_advocacy_language = verification
    elif check_type == "subjective_tone":
        result_obj.llm_subjective_tone = verification
