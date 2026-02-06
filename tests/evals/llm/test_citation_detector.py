from pathlib import Path

import pytest

from lib.agents.citation_detector import (
    BatchedCitationResult,
    CitationDetectorAgent,
    CitationDetectorPromptKwargs,
)
from lib.models.agent_test_case import AgentTestCase
from lib.models.footnote_item import FootnoteItem
from lib.workflows.citation_detection.nodes.detect_citations import (
    _format_bibliography,
    _format_footnotes_list,
)
from lib.workflows.reference_extraction.state import ExtractedReference
from tests.conftest import create_test_context
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases() -> list[AgentTestCase]:
    # Load dataset from YAML
    dataset_path = str(TESTS_DIR / "datasets" / "citation_detector.yaml")
    dataset = load_dataset(dataset_path)

    test_config = dataset.test_config
    if test_config:
        strict_fields = test_config.strict_fields or set()
        llm_fields = test_config.llm_fields or set()

    cases: list[AgentTestCase] = []

    for test_case in dataset.items:
        footnotes = test_case.input.get("footnotes", [])
        footnote_items = [FootnoteItem.model_validate(fn) for fn in footnotes]
        footnotes_list = _format_footnotes_list(footnote_items)

        bibliography = test_case.input.get("bibliography", [])
        bibliography_items = [
            ExtractedReference(id=f"bibliography-{i+1}", text=ref)
            for i, ref in enumerate(bibliography)
        ]
        bibliography_list = _format_bibliography(bibliography_items)

        # Wrap single chunk in batch format: list of (chunk_index, content) tuples
        chunk_content = test_case.input["chunk"]
        input_kwargs: CitationDetectorPromptKwargs = {
            "footnotes_list": footnotes_list,
            "bibliography": bibliography_list,
            "chunks": [(0, chunk_content)],
        }

        # Wrap expected output in batched format with single chunk at index 0
        batched_expected = {
            "results": [
                {
                    "chunk_index": 0,
                    **test_case.expected_output,
                }
            ]
        }

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=CitationDetectorAgent(create_test_context()),
                response_model=BatchedCitationResult,
                prompt_kwargs=input_kwargs,
                expected_dict=batched_expected,
                strict_fields=strict_fields,
                llm_fields=llm_fields,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases(), ids=lambda case: case.name)
async def test_citation_detector_agent_cases(case: AgentTestCase, test_models):
    await case.run(models=test_models)
    result = await case.compare_results()
    assert result.passed, f"{case.name}: {result.rationale}"
