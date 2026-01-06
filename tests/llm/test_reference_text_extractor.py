"""Tests for the ReferenceTextExtractorAgent.

Tests that the agent correctly extracts bibliographic reference text from documents.
Matching references to supporting documents is tested separately in workflow tests.
"""

from pathlib import Path

import pytest

from lib.agents.reference_text_extractor import (
    ReferenceTextExtractorAgent,
    ReferenceTextExtractorResponse,
)
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import create_test_context
from tests.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    """Build test cases from YAML dataset."""
    dataset_path = str(TESTS_DIR / "datasets" / "reference_text_extractor.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    strict_fields = test_config.strict_fields if test_config else set()
    llm_fields = test_config.llm_fields if test_config else set()

    cases: list[AgentTestCase] = []
    for test_case in dataset.items:
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=ReferenceTextExtractorAgent(create_test_context()),
                response_model=ReferenceTextExtractorResponse,
                prompt_kwargs={"text": test_case.input["text"]},
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_reference_text_extractor(case: AgentTestCase, test_models):
    """Test reference text extraction from various document formats."""
    await case.run(models=test_models)
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"

