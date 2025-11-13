import asyncio
from pathlib import Path

import pytest

from lib.agents.citation_suggester import (
    CitationSuggestionResponse,
    citation_suggester_agent,
)
from lib.agents.reference_extractor import BibliographyItem
from lib.agents.formatting_utils import format_bibliography_prompt_section
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import (
    extract_paragraph_from_chunk,
    create_test_file_document_from_path,
    TESTS_DIR,
)
from tests.datasets.loader import load_dataset


def _build_cases() -> list[AgentTestCase]:
    dataset_path = str(TESTS_DIR / "datasets" / "citation_suggester.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    strict_fields = test_config.strict_fields or set() if test_config else set()
    llm_fields = test_config.llm_fields or set() if test_config else set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        # Load main document
        main_doc = asyncio.run(
            create_test_file_document_from_path(test_case.input["main_document"])
        )

        # Inputs from dataset
        chunk = test_case.input["chunk"]
        claim_text = test_case.input["claim"]
        literature_review_input = test_case.input.get("literature_review_report", "")

        # Resolve literature review: if it's a file path (under tests/), read content
        literature_review_report = literature_review_input
        if isinstance(
            literature_review_input, str
        ) and literature_review_input.endswith((".md", ".txt")):
            lit_path = TESTS_DIR / literature_review_input
            if lit_path.exists():
                literature_review_report = lit_path.read_text(encoding="utf-8")

        # Build paragraph context from chunk
        paragraph = extract_paragraph_from_chunk(main_doc.markdown, chunk)

        # Build bibliography section using BibliographyItem models
        reference_items = [
            BibliographyItem(**ref) for ref in test_case.input["references"]
        ]
        bibliography_str = format_bibliography_prompt_section(
            reference_items, supporting_documents_summaries=None
        )

        # Build cited references block (default to explicit "no citations" text)
        cited_block = test_case.input.get("cited_references_block")
        if not cited_block:
            cited_block = "No reference is cited as support for this claim.\n\n"

        prompt_kwargs = {
            "full_document": main_doc.markdown,
            "bibliography": bibliography_str,
            "paragraph": paragraph,
            "chunk": chunk,
            "claim": claim_text,
            "cited_references": cited_block,
            "literature_review_report": literature_review_report,
        }

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=citation_suggester_agent,
                response_model=CitationSuggestionResponse,
                prompt_kwargs=prompt_kwargs,
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_citation_suggester_agent_cases(case: AgentTestCase):
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
