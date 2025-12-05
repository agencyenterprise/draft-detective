from pathlib import Path

import pytest

from lib.models.agent_test_case import AgentTestCase
from lib.workflows.reference_downloader.agents.reference_fetcher import (
    ReferenceFetcherAgent,
    ReferenceFetcherAgentInput,
    ReferenceFetchItem,
)
from tests.conftest import create_test_context
from tests.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "reference_fetcher.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=ReferenceFetcherAgent(create_test_context()),
                response_model=ReferenceFetchItem,
                prompt_kwargs=ReferenceFetcherAgentInput(**test_case.input),
                expected_dict=test_case.expected_output,
                strict_fields=test_config.strict_fields,
                llm_fields=test_config.llm_fields,
                ignore_fields=test_config.ignore_fields,
                llm_instructions=test_config.llm_instructions,
                fuzzy_threshold=0.9,
                good_match_threshold=0.99,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_reference_fetcher_agent_cases(case: AgentTestCase, test_models):
    await case.run(models=test_models)
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
