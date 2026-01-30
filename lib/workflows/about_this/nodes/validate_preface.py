"""
About This (Preface) Validation Node

Validates preface/introduction sections against 6 publication requirements:
1. Establishes context (sentence-level)
2. Explains objectives (sentence-level)
3. Explains relationship to RAND work (sentence-level)
4. Identifies intended audience (sentence-level)
5. Contains TASP boilerplate (paragraph-level)
6. Contains funding statement (paragraph-level)
"""

import logging
import re
from typing import List, Optional

import nltk

from langgraph.runtime import Runtime

from lib.agents.preface_requirement_checker import (
    PrefaceRequirementCheckerAgent,
    PrefaceRequirementType,
)
from lib.agents.preface_section_extractor import PrefaceSectionExtractorAgent
from lib.run_utils import run_tasks
from lib.workflows.about_this.constants import REQUIREMENT_METADATA
from lib.workflows.about_this.state import AboutThisState, RequirementCheckResult
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)

# Config mapping: (field_name, requirement_type, text_level)
# text_level determines whether to check sentences or paragraphs
REQUIREMENT_CHECK_CONFIG = [
    ("context", PrefaceRequirementType.CONTEXT, "sentences"),
    ("objectives", PrefaceRequirementType.OBJECTIVES, "sentences"),
    ("relationship", PrefaceRequirementType.RELATIONSHIP, "sentences"),
    ("audience", PrefaceRequirementType.AUDIENCE, "sentences"),
    ("source_tasp", PrefaceRequirementType.SOURCE_TASP, "paragraphs"),
    ("source_funding", PrefaceRequirementType.SOURCE_FUNDING, "paragraphs"),
]


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK."""
    if not text.strip():
        return []
    return nltk.sent_tokenize(text)


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs (on double newlines or significant breaks)."""
    if not text.strip():
        return []

    # Split on double newlines or multiple newlines
    paragraphs = re.split(r"\n\s*\n", text)

    # Filter out empty paragraphs and strip whitespace
    return [p.strip() for p in paragraphs if p.strip()]


def _to_requirement_result(
    result: Optional[object],
    text_items: List[str],
    default_explanation: str,
) -> RequirementCheckResult:
    """Convert LLM response to RequirementCheckResult."""
    if result is None:
        return RequirementCheckResult(
            passed=False,
            explanation=f"Error: {default_explanation}",
            matched_index=-1,
            matched_text="",
        )

    # Adjust index from 1-indexed to 0-indexed
    matched_index = result.matched_index - 1 if result.matched_index > 0 else -1
    matched_text = ""
    if 0 <= matched_index < len(text_items):
        matched_text = text_items[matched_index]

    return RequirementCheckResult(
        passed=result.passed,
        explanation=result.explanation,
        matched_index=matched_index,
        matched_text=matched_text,
    )


@register_node(
    "Validate preface section",
    "Check preface against 6 publication requirements",
)
async def validate_preface(state: AboutThisState, runtime: Runtime[ContextSchema]):
    """Main validation node: extracts preface and validates against all requirements."""

    context = runtime.context

    # Step 1: Extract preface section using agentic agent
    logger.info("[AboutThis] Extracting preface section...")
    extractor = PrefaceSectionExtractorAgent(context)
    extraction_result = await extractor.ainvoke({})

    logger.info(f"[AboutThis] Search result: {extraction_result.reasoning[:200]}...")

    if not extraction_result.found_section:
        logger.info("[AboutThis] No preface/introduction section found")
        return {
            "found_section": False,
            "section_title": "",
            "section_text": "",
            "overall_passed": False,
            "final_summary": "No preface or 'About This Report' section was found in the document.",
        }

    section_title = extraction_result.section_title
    section_text = extraction_result.section_text

    logger.info(
        f"[AboutThis] Found section: '{section_title}' ({len(section_text)} chars)"
    )

    # Step 2: Split into sentences and paragraphs
    sentences = _split_into_sentences(section_text)
    paragraphs = _split_into_paragraphs(section_text)

    logger.info(
        f"[AboutThis] Split into {len(sentences)} sentences, {len(paragraphs)} paragraphs"
    )

    if not sentences:
        logger.warning("[AboutThis] No sentences found in section")
        return {
            "found_section": True,
            "section_title": section_title,
            "section_text": section_text,
            "overall_passed": False,
            "final_summary": "The preface section appears to be empty or unparseable.",
        }

    # Step 3: Run all checks in parallel
    checker = PrefaceRequirementCheckerAgent(context)
    text_items_map = {"sentences": sentences, "paragraphs": paragraphs}

    tasks = [
        checker.ainvoke(
            {"text_items": text_items_map[level], "requirement_type": req_type}
        )
        for _, req_type, level in REQUIREMENT_CHECK_CONFIG
    ]

    results, _ = await run_tasks(tasks, desc="Checking preface requirements")

    # Step 4: Convert results to RequirementCheckResult
    requirement_results = {}
    for i, (field, _, level) in enumerate(REQUIREMENT_CHECK_CONFIG):
        text_items = text_items_map[level]
        meta = REQUIREMENT_METADATA[field]
        requirement_results[field] = _to_requirement_result(
            results[i], text_items, f"Failed to check {meta['name'].lower()}"
        )

    # Step 5: Determine overall pass/fail and generate summary
    failed_requirements = []
    for field, result in requirement_results.items():
        if not result.passed:
            meta = REQUIREMENT_METADATA[field]
            failed_requirements.append(f"• {meta['name']}: {result.explanation}")

    all_passed = len(failed_requirements) == 0
    passed_count = len(requirement_results) - len(failed_requirements)

    if all_passed:
        final_summary = "All preface requirements passed."
    else:
        final_summary = (
            f"The preface section failed {len(failed_requirements)} requirement(s):\n"
            + "\n".join(failed_requirements)
        )

    logger.info(
        f"[AboutThis] Results: {passed_count}/{len(requirement_results)} requirements passed, "
        f"overall: {'PASS' if all_passed else 'FAIL'}"
    )

    return {
        "found_section": True,
        "section_title": section_title,
        "section_text": section_text,
        **requirement_results,
        "overall_passed": all_passed,
        "final_summary": final_summary,
    }
