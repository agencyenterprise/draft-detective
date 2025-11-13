"""Tests for inference validator agent using Toulmin argumentation model."""

import asyncio
import pytest

from lib.agents.formatting_utils import (
    format_audience_context,
    format_domain_context,
)
from lib.agents.inference_validator import (
    InferenceValidationResponse,
    inference_validator_agent,
)
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import (
    TESTS_DIR,
    extract_paragraph_from_chunk,
    create_test_file_document_from_path,
)
from tests.datasets.loader import load_dataset


def _build_cases():
    """Build test cases from inference validator dataset."""

    dataset_path = str(TESTS_DIR / "datasets" / "inference_validator.yaml")
    dataset = load_dataset(dataset_path)

    # Get test configuration from dataset
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
        paragraph = test_case.input.get("paragraph", "")
        chunk = test_case.input.get("chunk")
        claim = test_case.input.get("claim")
        domain = test_case.input.get("domain")
        target_audience = test_case.input.get("target_audience")

        # Try to extract paragraph from document if not provided
        if not paragraph and chunk:
            try:
                paragraph = extract_paragraph_from_chunk(main_doc.markdown, chunk)
            except ValueError:
                # If chunk not found, use chunk as paragraph
                paragraph = chunk

        # Build prompt kwargs - note: inference validator needs claim_index and chunk_index
        # For these tests we'll use dummy indices since we're testing the agent in isolation
        prompt_kwargs = {
            "full_document": main_doc.markdown,
            "paragraph": paragraph,
            "chunk": chunk,
            "claim": claim,
            "domain_context": format_domain_context(domain),
            "audience_context": format_audience_context(target_audience),
            "claim_index": 0,  # Dummy index for testing
            "chunk_index": 0,  # Dummy index for testing
        }

        # Build test case
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=inference_validator_agent,
                response_model=InferenceValidationResponse,
                prompt_kwargs=prompt_kwargs,
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_inference_validator(case):
    """Test inference validator agent."""
    await case.run()
    eval_result = await case.compare_results()
    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
