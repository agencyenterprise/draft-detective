"""Basic claim categorizer tests."""

import asyncio
import pytest

from lib.agents.claim_categorizer import (
    ClaimCategorizationResponse,
    claim_categorizer_agent,
)
from lib.agents.formatting_utils import (
    format_audience_context,
    format_domain_context,
)
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import (
    TESTS_DIR,
    extract_paragraph_from_chunk,
    create_test_file_document_from_path,
)
from tests.datasets.loader import load_dataset


def _build_cases():
    """Build test cases from basic dataset."""

    dataset_path = str(TESTS_DIR / "datasets" / "claim_categorizer.yaml")
    dataset = load_dataset(dataset_path)

    # Get test configuration from dataset, with defaults if not present
    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        # Load main document
        main_doc = asyncio.run(
            create_test_file_document_from_path(test_case.input["main_document"])
        )

        # Extract inputs
        chunk = test_case.input.get("chunk")
        claim = test_case.input.get("claim")
        domain = test_case.input.get("domain")
        target_audience = test_case.input.get("target_audience")
        try:
            paragraph = extract_paragraph_from_chunk(main_doc.markdown, chunk)
        except ValueError:
            paragraph = ""

        # Build prompt kwargs
        prompt_kwargs = {
            "full_document": main_doc.markdown,
            "paragraph": paragraph,
            "chunk": chunk,
            "claim": claim,
            "domain_context": format_domain_context(domain),
            "audience_context": format_audience_context(target_audience),
        }

        # Build test case
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=claim_categorizer_agent,
                response_model=ClaimCategorizationResponse,
                prompt_kwargs=prompt_kwargs,
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_claim_categorizer(case):
    """Test claim categorizer."""
    await case.run()
    eval_result = await case.compare_results()
    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
