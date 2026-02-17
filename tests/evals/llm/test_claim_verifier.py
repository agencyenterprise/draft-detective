"""Agentic claim verification tests using vector search.

This test suite verifies claims using the agentic ClaimVerifierAgent,
which uses vector_search tool calls to retrieve evidence from supporting
documents indexed in the vector store.
"""

import asyncio
from pathlib import Path

import pytest

from lib.agents.claim_verifier import (
    ClaimVerifierAgent,
    ParagraphVerificationResult,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.models.agent_test_case import AgentTestCase
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.services.vector_store import get_collection_id, get_file_hash_from_path
from tests.conftest import (
    create_test_context,
    create_test_file_document_from_path,
    extract_paragraph_from_chunk,
)
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent


def _remap_fields_to_nested(fields: set | dict | None) -> dict:
    """Remap flat field names to nested claim_results array format.

    The dataset defines fields like {'evidence_alignment'} for the old flat model.
    The new ParagraphVerificationResult wraps results in claim_results[],
    so we remap to {'claim_results': ['evidence_alignment']}.
    """
    if not fields:
        return {}
    if isinstance(fields, set):
        return {"claim_results": list(fields)}
    # Already a dict -- wrap values under claim_results
    return {"claim_results": fields}


def _build_citation_file_mapping_for_test(supporting_docs) -> str:
    """Build a citation-to-file mapping that lists all supporting files.

    In tests, we don't have real citation-bibliography-file chains,
    so we list all supporting files directly for the agent to search.
    """
    if not supporting_docs:
        return "No supporting files available."

    lines = []
    for doc in supporting_docs:
        lines.append(f'- File: "{doc.file_name}" (file_id: {doc.file_id})')
    return "\n".join(lines)


async def _build_cases(dataset_file_name: str):
    """Build test cases from dataset."""

    dataset_path = str(TESTS_DIR / "datasets" / dataset_file_name)
    dataset = load_dataset(dataset_path)
    cases: list[AgentTestCase] = []

    # Collect all supporting documents and index them once
    supporting_docs_set = set()
    for test_case in dataset.items:
        supporting_docs_set.update(test_case.input.get("supporting_documents", []))

    from lib.config.env import config
    from lib.services.vector_store import VectorStoreService

    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set")

    vector_store = VectorStoreService(config.DATABASE_URL, config.OPENAI_API_KEY)

    for supporting_doc in supporting_docs_set:
        file_doc = await create_test_file_document_from_path(supporting_doc)
        collection_id = get_collection_id(get_file_hash_from_path(file_doc.file_path))
        await vector_store.ensure_collection_indexed(
            collection_id=collection_id,
            markdown_content=file_doc.markdown,
            file_name=file_doc.file_name,
        )

    for test_case in dataset.items:
        # Load main document
        main_doc = await create_test_file_document_from_path(
            test_case.input["main_document"]
        )

        # Build supporting documents
        supporting_docs = [
            await create_test_file_document_from_path(supporting_doc)
            for supporting_doc in test_case.input.get("supporting_documents", [])
        ]

        # Extract inputs
        chunk = test_case.input["chunk"]
        claim_text = test_case.input["claim"]
        domain = test_case.input.get("domain")
        target_audience = test_case.input.get("target_audience")
        paragraph = extract_paragraph_from_chunk(main_doc.markdown, chunk)

        # Build the citation-to-file mapping for the agent
        citation_file_mapping = _build_citation_file_mapping_for_test(supporting_docs)

        # Create context with supporting files available to the vector_search tool
        mock_service = MockFileArtifactsService(
            main_file=main_doc,
            supporting_files=supporting_docs,
        )
        context = create_test_context(file_artifacts_service=mock_service)

        # Build prompt kwargs for the new agent
        prompt_kwargs = {
            "paragraph": paragraph,
            "claims_list": f"1. {claim_text}",
            "citation_file_mapping": citation_file_mapping,
            "domain_context": format_domain_context(domain),
            "audience_context": format_audience_context(target_audience),
        }

        # Wrap expected output in ParagraphVerificationResult format
        expected_dict = {
            "claim_results": [
                {
                    "claim_number": 1,
                    **test_case.expected_output,
                }
            ]
        }

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=ClaimVerifierAgent(context),
                response_model=ParagraphVerificationResult,
                prompt_kwargs=prompt_kwargs,
                expected_dict=expected_dict,
                strict_fields=_remap_fields_to_nested(
                    dataset.test_config.strict_fields
                ),
                llm_fields=_remap_fields_to_nested(dataset.test_config.llm_fields),
            )
        )

    return cases


def _build_cases_sync(dataset_file_name: str):
    return asyncio.run(_build_cases(dataset_file_name))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", _build_cases_sync("claim_verifier.yaml"), ids=lambda case: case.name
)
async def test_claim_verifier_rag(case: AgentTestCase, test_models):
    """Test agentic claim verification with vector search.

    These tests use the ClaimVerifierAgent with vector_search tool to
    retrieve evidence from indexed supporting documents.
    """
    await case.run(models=test_models)
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _build_cases_sync("rag_stress_tests.yaml"),
    ids=lambda case: case.name,
)
async def test_claim_verifier_rag_stress_tests(case: AgentTestCase, test_models):
    """Test agentic claim verification stress test cases."""
    await case.run(models=test_models)
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
