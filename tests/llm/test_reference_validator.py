from pathlib import Path

import pytest

from lib.agents.reference_validator import (
    BibliographyValidationResponse,
    reference_validator_agent,
)
from lib.models.agent_test_case import AgentTestCase
from tests.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "reference_validator.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=reference_validator_agent,
                response_model=BibliographyValidationResponse,
                prompt_kwargs={
                    "references": test_case.input.get("references", []),
                },
                expected_dict=test_case.expected_output,
                strict_fields=test_config.strict_fields,
                llm_fields=test_config.llm_fields,
                ignore_fields=test_config.ignore_fields,
                llm_instructions=test_config.llm_instructions,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_reference_validator_agent_cases(case: AgentTestCase):
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
