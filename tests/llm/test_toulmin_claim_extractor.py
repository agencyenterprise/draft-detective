import asyncio
from pathlib import Path

import pytest

from lib.models.agent_test_case import AgentTestCase
from lib.services.file import create_file_document_from_path
from lib.agents.toulmin_claim_extractor import (
    ToulminClaimResponse,
    toulmin_claim_extractor_agent,
)
from lib.agents.formatting_utils import format_domain_context, format_audience_context
from tests.conftest import data_path, extract_paragraph_from_chunk
from tests.datasets.loader import load_dataset


TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "toulmin_claim_extractor.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        # Load main document from input
        main_path = data_path(test_case.input["main_document"])
        main_doc = asyncio.run(create_file_document_from_path(main_path))

        domain = test_case.input.get("domain")
        target_audience = test_case.input.get("target_audience")
        chunk = test_case.input["chunk"]
        paragraph = extract_paragraph_from_chunk(main_doc.markdown, chunk)

        cases.append(
            AgentTestCase(
                name=test_case.name,
                # agent=claim_extractor_agent,
                # response_model=ClaimResponse,
                agent=toulmin_claim_extractor_agent,
                response_model=ToulminClaimResponse,
                prompt_kwargs={
                    "full_document": main_doc.markdown,
                    "paragraph": paragraph,
                    "chunk": chunk,
                    "domain_context": format_domain_context(domain),
                    "audience_context": format_audience_context(target_audience),
                },
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_claim_extractor_agent_cases(case: AgentTestCase):
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
