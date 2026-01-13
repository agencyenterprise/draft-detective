import asyncio
from pathlib import Path

import pytest

from lib.agents.citation_detector import CitationResponse
from lib.agents.citation_detector_footnotes import CitationDetectorFootnotesAgent
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import (
    create_test_file_document_from_path,
    data_path,
    create_test_context,
)
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _format_footnotes_list(footnotes_data):
    """Format footnotes list for the agent prompt."""
    if not footnotes_data:
        return "No footnotes available."
    lines = []
    for fn in footnotes_data:
        lines.append(f"[{fn['marker']}]. {fn['text']}")
    return "\n".join(lines)


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "citation_detector_footnotes.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        # Load main document from input
        main_path = data_path(test_case.input["main_document"])
        main_doc = asyncio.run(create_test_file_document_from_path(main_path))

        # Format footnotes list
        footnotes_list = _format_footnotes_list(test_case.input.get("footnotes", []))

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=CitationDetectorFootnotesAgent(create_test_context()),
                response_model=CitationResponse,
                prompt_kwargs={
                    "footnotes_list": footnotes_list,
                    "bibliography": "\n\n".join(
                        f"{i+1}. {ref}"
                        for i, ref in enumerate(test_case.input["bibliography"])
                    ),
                    "chunk": test_case.input["chunk"],
                },
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_citation_detector_footnotes(case: AgentTestCase):
    """Test citation detector with footnotes agent."""
    await case.run()
    result = await case.compare_results()
    assert result.passed, f"Test {case.name} failed: {result.rationale}"
