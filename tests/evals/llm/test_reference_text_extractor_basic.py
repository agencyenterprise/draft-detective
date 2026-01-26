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
from lib.agents.reference_text_extractor_v2 import (
    ReferenceExtractorV2Agent,
    ReferenceExtractorV2Output,
)
from lib.models.agent_test_case import AgentTestCase
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from tests.conftest import create_test_context
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _build_cases_v1() -> list[AgentTestCase]:
    """Build test cases from YAML dataset."""
    dataset_path = str(TESTS_DIR / "datasets" / "reference_text_extractor.yaml")
    dataset = load_dataset(dataset_path)

    cases: list[AgentTestCase] = []
    for test_case in dataset.items:
        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=ReferenceTextExtractorAgent(create_test_context()),
                response_model=ReferenceTextExtractorResponse,
                prompt_kwargs={"text": test_case.input["text"]},
                expected_dict=test_case.expected_output,
                strict_fields=dataset.test_config.strict_fields,
                llm_fields=dataset.test_config.llm_fields,
            )
        )

    return cases


def _build_cases_v2() -> list[AgentTestCase]:
    """Build test cases from YAML dataset."""
    dataset_path = str(TESTS_DIR / "datasets" / "reference_text_extractor.yaml")
    dataset = load_dataset(dataset_path)

    cases: list[AgentTestCase] = []
    for test_case in dataset.items:
        file_artifacts_service = MockFileArtifactsService(
            main_file=FileDocument(
                markdown=test_case.input["text"],
                file_name="test.md",
                file_path="test.md",
                file_type="text/markdown",
                markdown_token_count=len(test_case.input["text"]),
                file_id="test_file_id",
            )
        )

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=ReferenceExtractorV2Agent(
                    create_test_context(file_artifacts_service)
                ),
                response_model=ReferenceExtractorV2Output,
                prompt_kwargs={},
                expected_dict=test_case.expected_output,
                strict_fields=dataset.test_config.strict_fields,
                llm_fields=dataset.test_config.llm_fields,
                fuzzy_threshold=1.0,
                good_match_threshold=1.0,
            )
        )

    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases_v1(), ids=lambda case: case.name)
async def test_reference_text_extractor_basic_v1(case: AgentTestCase, test_models):
    """Test reference text extraction from various document formats."""

    await case.run(models=test_models)
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _build_cases_v2(), ids=lambda case: case.name)
async def test_reference_text_extractor_basic_v2(case: AgentTestCase, test_models):
    """Test reference text extraction from various document formats."""

    await case.run(models=test_models)
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
