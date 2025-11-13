import asyncio
from pathlib import Path

import pytest

from lib.agents.reference_extractor import (
    ReferenceExtractorResponse,
    reference_extractor_agent,
)
from lib.agents.formatting_utils import (
    format_supporting_documents_prompt_section_multiple,
)
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import create_test_file_document_from_path, data_path
from tests.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


async def _build_supporting_block(paths: list[str]) -> str:
    docs = [await create_test_file_document_from_path(data_path(p)) for p in paths]
    return format_supporting_documents_prompt_section_multiple(
        docs, truncate_at_character_count=1000
    )


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "reference_extractor.yaml")
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

        # Build supporting documents block from input
        supporting_block = asyncio.run(
            _build_supporting_block(test_case.input["supporting_documents"])
        )

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=reference_extractor_agent,
                response_model=ReferenceExtractorResponse,
                prompt_kwargs={
                    "full_document": main_doc.markdown,
                    "supporting_documents": supporting_block,
                },
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_reference_extractor_agent_cases(case: AgentTestCase):
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
