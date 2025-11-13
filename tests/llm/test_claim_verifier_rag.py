"""RAG-based claim substantiation tests.

This test suite uses RAG (Retrieval Augmented Generation) for claim verification,
which retrieves relevant passages from supporting documents instead of passing
full documents in the prompt. Results can be compared with test_claim_verifier.py
to evaluate the effectiveness of the RAG approach.
"""

import asyncio
from typing import List, Set

import pytest

from lib.agents.citation_detector import Citation
from lib.agents.claim_extractor import Claim, ClaimResponse
from lib.agents.claim_verifier import ClaimSubstantiationResult, claim_verifier_agent
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.agents.reference_extractor import BibliographyItem
from lib.config.logger import setup_logger
from lib.models.agent_test_case import AgentTestCase
from lib.services.file import FileDocument
from lib.workflows.claim_substantiation.nodes.index_supporting_documents import (
    index_file_document,
)
from lib.workflows.claim_substantiation.nodes.verify_claims import (
    format_evidence_explanation,
)
from lib.workflows.claim_substantiation.reference_providers import RAGReferenceProvider
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
    SubstantiationWorkflowConfig,
)
from tests.conftest import (
    TESTS_DIR,
    extract_paragraph_from_chunk,
    create_test_file_document_from_path,
)
from tests.datasets.loader import load_dataset

setup_logger()


class TestRAGReferenceProvider(RAGReferenceProvider):
    """
    Extension of the original RAG reference provider for testing purposes.

    We override the `_get_supporting_files_for_citations` method to return all available supporting files from the state,
    so we don't need to provide references and references in the test cases.
    """

    def _get_supporting_files_for_citations(
        self,
        supporting_files: List[FileDocument],
        references: List[BibliographyItem],
        citations: List[Citation],
    ) -> Set[FileDocument]:
        """
        Return all available supporting files from the state.

        We do that so we don't need to provide references and citations in the test cases.
        ALL supporting files defined in the test case will be used to verify the claim.
        """

        return set(supporting_files)


async def _build_cases(dataset_file_name: str):
    """Build test cases from basic dataset."""

    dataset_path = str(TESTS_DIR / "datasets" / dataset_file_name)
    dataset = load_dataset(dataset_path)
    cases: list[AgentTestCase] = []

    # Collect all supporting documents and index them at once to avoid creating duplicate embeddings due to test parallelism
    supporting_docs_set = set()
    for test_case in dataset.items:
        supporting_docs_set.update(test_case.input.get("supporting_documents", []))
    for supporting_doc in supporting_docs_set:
        file_doc = await create_test_file_document_from_path(supporting_doc)
        await index_file_document(file_doc)

    for test_case in dataset.items:
        # Load main document
        main_doc = await create_test_file_document_from_path(
            test_case.input["main_document"]
        )

        # Build supporting documents block if provided
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

        # Create state and index supporting documents
        state = ClaimSubstantiatorState(
            file=main_doc,
            supporting_files=supporting_docs,
            config=SubstantiationWorkflowConfig(
                use_rag=True, domain=domain, target_audience=target_audience
            ),
        )

        # Instantiate RAG Reference Provider, mock inputs unused by this test
        reference_provider = TestRAGReferenceProvider()
        claim1 = Claim(claim=claim_text, text=chunk, rationale="")
        ref_context = await reference_provider.get_references_for_claim(
            state,
            DocumentChunk(
                claims=ClaimResponse(claims=[claim1], rationale=""),
                content=chunk,
                chunk_index=0,
                paragraph_index=0,
            ),
            claim1,
            0,
        )

        # Build prompt kwargs
        prompt_kwargs = {
            "full_document": main_doc.markdown,
            "paragraph": paragraph,
            "chunk": chunk,
            "claim": claim_text,
            "evidence_context_explanation": format_evidence_explanation(True),
            "cited_references": ref_context.cited_references,
            "cited_references_paragraph": ref_context.cited_references_paragraph,
            "domain_context": format_domain_context(domain),
            "audience_context": format_audience_context(target_audience),
        }

        cases.append(
            AgentTestCase(
                name=test_case.name,
                agent=claim_verifier_agent,
                response_model=ClaimSubstantiationResult,
                prompt_kwargs=prompt_kwargs,
                expected_dict=test_case.expected_output,
                strict_fields=dataset.test_config.strict_fields or set(),
                llm_fields=dataset.test_config.llm_fields or set(),
            )
        )

    return cases


def _build_cases_sync(dataset_file_name: str):
    return asyncio.run(_build_cases(dataset_file_name))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", _build_cases_sync("claim_verifier.yaml"), ids=lambda case: case.name
)
async def test_claim_verifier_rag(case: AgentTestCase):
    """Test RAG-based claim substantiation cases.

    These tests use the same dataset and evaluation criteria as test_claim_verifier.py,
    allowing for direct comparison between the full-text and RAG approaches.
    """
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _build_cases_sync("rag_stress_tests.yaml"),
    ids=lambda case: case.name,
)
async def test_claim_verifier_rag_stress_tests(case: AgentTestCase):
    """Test RAG-based claim substantiation stress test cases."""
    await case.run()
    eval_result = await case.compare_results()

    assert eval_result.passed, f"{case.name}: {eval_result.rationale}"
