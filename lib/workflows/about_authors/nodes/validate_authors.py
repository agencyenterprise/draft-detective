"""
About Authors Validation Node

Validates author bios against 5 publication rules:
1. Exactly 3 sentences
2. Position + affiliation
3. TASP statement (if TASP fellow)
4. Research focus
5. Highest degree
"""

import logging
from typing import List

import nltk

from langgraph.runtime import Runtime

from lib.agents.author_bio_extractor import AuthorBioExtractorAgent
from lib.agents.author_final_judge import AuthorFinalJudgeAgent
from lib.agents.author_name_extractor import AuthorNameExtractorAgent
from lib.agents.author_rule_checker import AuthorRuleCheckerAgent, AuthorRuleType
from lib.run_utils import run_tasks
from lib.workflows.about_authors.constants import (
    ABBREVIATIONS,
    EXPECTED_SENTENCE_COUNT,
    IGNORE_SENTENCE_PATTERNS,
    RULE_FIELDS,
    RULE_METADATA,
)
from lib.workflows.about_authors.state import (
    AboutAuthorsState,
    AuthorValidationResult,
    RuleCheckResult,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


# ============================================================================
# Sentence Counting (Rule 1 - procedural)
# ============================================================================


def _count_sentences(text: str) -> int:
    """Count sentences using NLTK, handling abbreviations."""
    cleaned = text

    for pattern in IGNORE_SENTENCE_PATTERNS:
        cleaned = cleaned.replace(pattern, "")

    for abbrev in ABBREVIATIONS:
        cleaned = cleaned.replace(abbrev, abbrev.replace(".", ""))

    return len(nltk.sent_tokenize(cleaned))


# ============================================================================
# Single Author Validation
# ============================================================================


async def _validate_single_author(
    author_id: str,
    author_text: str,
    name_agent: AuthorNameExtractorAgent,
    rule_agent: AuthorRuleCheckerAgent,
    judge_agent: AuthorFinalJudgeAgent,
) -> AuthorValidationResult:
    """Validate a single author bio against all 5 rules."""

    # Step 1: Extract author name
    name_result = await name_agent.ainvoke({"author_text": author_text})
    author_name = name_result.name
    name_positions = name_result.positions

    # Step 2: Rule 1 - Sentence count (procedural)
    sentence_count = _count_sentences(author_text)
    rule_1 = RuleCheckResult(
        passed=(sentence_count == EXPECTED_SENTENCE_COUNT),
        explanation=(
            "PASS"
            if sentence_count == EXPECTED_SENTENCE_COUNT
            else f"FAIL: Contains {sentence_count} sentences (expected {EXPECTED_SENTENCE_COUNT})"
        ),
    )

    # Step 3: Parallel LLM checks for Rules 2-5 + TASP check
    rule_tasks = [
        rule_agent.ainvoke(
            {
                "author_text": author_text,
                "rule_type": AuthorRuleType.POSITION_AFFILIATION,
            }
        ),
        rule_agent.ainvoke(
            {"author_text": author_text, "rule_type": AuthorRuleType.TASP_FELLOW}
        ),
        rule_agent.ainvoke(
            {"author_text": author_text, "rule_type": AuthorRuleType.TASP_STATEMENT}
        ),
        rule_agent.ainvoke(
            {"author_text": author_text, "rule_type": AuthorRuleType.RESEARCH_FOCUS}
        ),
        rule_agent.ainvoke(
            {"author_text": author_text, "rule_type": AuthorRuleType.HIGHEST_DEGREE}
        ),
    ]

    results, _ = await run_tasks(rule_tasks, desc=f"Checking rules for {author_name}")
    rule_2_raw, tasp_check_raw, rule_3_raw, rule_4_raw, rule_5_raw = results

    def to_rule_result(result, default_msg: str) -> RuleCheckResult:
        if result is None:
            return RuleCheckResult(passed=False, explanation=f"Error: {default_msg}")
        return RuleCheckResult(passed=result.passed, explanation=result.explanation)

    rule_2 = to_rule_result(rule_2_raw, "Failed to check position/affiliation")
    rule_4 = to_rule_result(rule_4_raw, "Failed to check research focus")
    rule_5 = to_rule_result(rule_5_raw, "Failed to check highest degree")

    # Rule 3 conditional logic (only applies if TASP fellow)
    is_tasp_fellow = tasp_check_raw.passed if tasp_check_raw else False
    if is_tasp_fellow:
        rule_3 = to_rule_result(rule_3_raw, "Failed to check TASP statement")
    else:
        rule_3 = RuleCheckResult(
            passed=True,
            explanation="N/A - Author is not a TASP fellow",
            applicable=False,
        )

    # Step 4: Determine overall pass/fail
    all_checks = [rule_1, rule_2, rule_3, rule_4, rule_5]
    applicable_checks = [r for r in all_checks if r.applicable]
    all_passed = all(r.passed for r in applicable_checks)

    # Step 5: Final judge (only if failed)
    if all_passed:
        final_comment = "PASS"
        guidance = None
    else:
        # Use centralized rule metadata for consistency
        failed_rules = [
            f"{RULE_METADATA[field]['name']}: {check.explanation}"
            for field, check in zip(RULE_FIELDS, all_checks)
            if check.applicable and not check.passed
        ]

        judge_result = await judge_agent.ainvoke(
            {"author_text": author_text, "failed_rules": failed_rules}
        )
        final_comment = f"FAIL: {judge_result.comment}"
        guidance = judge_result.guidance

    return AuthorValidationResult(
        author_id=author_id,
        author_text=author_text,
        author_name=author_name,
        author_name_positions=name_positions,
        chunk_indices=[],  # Not used with agentic approach
        rule_1_sentence_length=rule_1,
        rule_2_position_affiliation=rule_2,
        rule_3_tasp_statement=rule_3,
        rule_4_research_focus=rule_4,
        rule_5_highest_degree=rule_5,
        overall_passed=all_passed,
        final_comment=final_comment,
        guidance=guidance,
    )


# ============================================================================
# Main Node
# ============================================================================


@register_node(
    "Validate author biographies",
    "Check author bios against 5 publication rules",
)
async def validate_authors(state: AboutAuthorsState, runtime: Runtime[ContextSchema]):
    """Main validation node: extracts authors and validates each one."""

    # Extract author bios using agentic document search
    agent = AuthorBioExtractorAgent(runtime.context)
    result = await agent.ainvoke({})

    logger.info(f"[AboutAuthors] Search result: {result.reasoning[:200]}...")

    if not result.found_section:
        logger.info("[AboutAuthors] No 'About the Authors' section found")
        return {"results": []}

    if result.section_title:
        logger.info(f"[AboutAuthors] Found section: '{result.section_title}'")

    # Filter valid bios (> 50 chars)
    author_bios = [bio for bio in result.author_bios if len(bio.bio_text) > 50]

    if not author_bios:
        logger.info("[AboutAuthors] No valid author bios found in section")
        return {"results": []}

    logger.info(f"[AboutAuthors] Found {len(author_bios)} author bios")

    # Initialize validation agents
    name_agent = AuthorNameExtractorAgent(runtime.context)
    rule_agent = AuthorRuleCheckerAgent(runtime.context)
    judge_agent = AuthorFinalJudgeAgent(runtime.context)

    # Validate all authors in parallel
    validation_tasks = [
        _validate_single_author(
            author_id=f"author-{i}",
            author_text=bio.bio_text,
            name_agent=name_agent,
            rule_agent=rule_agent,
            judge_agent=judge_agent,
        )
        for i, bio in enumerate(author_bios)
    ]

    results, _ = await run_tasks(validation_tasks, desc="Validating author bios")
    valid_results = [r for r in results if r is not None]

    passed = sum(1 for r in valid_results if r.overall_passed)
    failed = len(valid_results) - passed
    logger.info(f"[AboutAuthors] Results: {passed} passed, {failed} failed")

    return {"results": valid_results}
