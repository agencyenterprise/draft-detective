from pathlib import Path

import pytest

from lib.agents.footnote_extractor import (
    FootnoteExtractorAgent,
    FootnoteExtractorResponse,
)
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import create_test_context
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "footnote_extractor.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()
        ignore_fields = test_config.ignore_fields or set()
        llm_instructions = test_config.llm_instructions
    else:
        strict_fields = set()
        llm_fields = set()
        ignore_fields = set()
        llm_instructions = None

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=FootnoteExtractorAgent(create_test_context()),
                response_model=FootnoteExtractorResponse,
                prompt_kwargs={"text": test_case.input["text"]},
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
                ignore_fields=ignore_fields,
                llm_instructions=llm_instructions,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_footnote_extractor(case: AgentTestCase):
    """Test footnote extractor agent."""
    await case.run()
    result = await case.compare_results()
    assert result.passed, f"Test {case.name} failed: {result.rationale}"
