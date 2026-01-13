"""
Regression test for footnote index mismatch bug.

This test verifies that the citation detector matches footnote markers like [10]
to bibliography entries based on CONTENT from the footnotes section, NOT by
their index position in the bibliography list.

BUG: In large documents, the system incorrectly matches [10] to bibliography
entry #10 by index, when the correct match should be determined by reading
the footnotes section of the document.

EXPECTED: [10] → Entry #42 (EIA-860), [11] → Entry #43 (DOE RFI)
ACTUAL (BUG): [10] → Entry #10 (Chang/Bloomberg), [11] → Entry #11 (Tesla)
"""

import asyncio
from pathlib import Path

import pytest

from lib.agents.citation_detector import CitationResponse, CitationDetectorAgent
from lib.models.agent_test_case import AgentTestCase
from tests.conftest import (
    create_test_file_document_from_path,
    data_path,
    create_test_context,
)
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(
        TESTS_DIR / "datasets" / "citation_detector_footnote_mismatch.yaml"
    )
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

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=CitationDetectorAgent(create_test_context()),
                response_model=CitationResponse,
                prompt_kwargs={
                    "full_document": main_doc.markdown,
                    "bibliography": "\n\n".join(
                        f"{i+1}. {ref}"
                        for i, ref in enumerate(test_case.input["bibliography"])
                    ),
                    "chunk": test_case.input["chunk"],
                    "feedback": "",
                },
                expected_dict=test_case.expected_output,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_citation_detector_footnote_mismatch(case: AgentTestCase, test_models):
    """
    Test that citation detector correctly matches footnote markers to bibliography
    entries based on content, not index position.

    This test is expected to FAIL with the current implementation because the
    LLM matches [10] to bibliography entry #10 by index instead of finding
    the correct entry (#42) based on the footnotes section content.
    """
    await case.run(models=test_models)
    result = await case.compare_results()
    assert result.passed, f"{case.name}: {result.rationale}"
