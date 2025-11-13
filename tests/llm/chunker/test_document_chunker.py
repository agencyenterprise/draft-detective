import asyncio
from pathlib import Path

import pytest

from lib.agents.document_chunker import DocumentChunkerResponse, document_chunker_agent
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import create_test_file_document_from_path, data_path
from tests.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "document_chunker.yaml")
    dataset = load_dataset(dataset_path)

    # Get test configuration from dataset, with defaults if not present
    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        # Load main document from input
        main_path = data_path(test_case.input["main_document"])
        main_doc = asyncio.run(create_test_file_document_from_path(main_path))

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=document_chunker_agent,
                response_model=DocumentChunkerResponse,
                prompt_kwargs={
                    "full_document": main_doc.markdown,
                },
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_document_chunker_agent_cases(case: AgentTestCase):
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
