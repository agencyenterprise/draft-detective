"""Test case builders for different agent types."""

from typing import Dict, List, Any, Union
from pydantic import BaseModel

from lib.agents.citation_detector import CitationResponse
from lib.agents.claim_extractor import ClaimResponse
from lib.agents.toulmin_claim_extractor import ToulminClaimResponse
from lib.models.bibliography_item import BibliographyItem


class TestDataPaths:
    """Utility class for generating test data file paths."""

    @staticmethod
    def main_document(test_name: str) -> str:
        return f"data/{test_name}/main_document.md"

    @staticmethod
    def supporting_documents(test_name: str, supporting_files: List) -> List[str]:
        return [
            f"data/{test_name}/supporting_{i+1}.md"
            for i, _ in enumerate(supporting_files)
        ]


def normalize_model_data(data: Union[BaseModel, Dict[str, Any]]) -> Dict[str, Any]:
    """Convert BaseModel to dict if needed, otherwise return as-is."""
    return data.model_dump() if isinstance(data, BaseModel) else data


class CitationTestCaseBuilder:
    """Builds test cases for citation detection."""

    @classmethod
    def build(
        cls,
        test_name: str,
        chunk_index: int,
        chunk_content: str,
        citations: Union[CitationResponse, Dict[str, Any]],
        references: List[Union[BibliographyItem, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Build citation test case with supporting documents (bibliography)."""
        # Extract bibliography from references for citation context
        bibliography = []
        for ref in references:
            if isinstance(ref, BaseModel):
                if hasattr(ref, "text") and ref.text:
                    bibliography.append(ref.text)
            elif isinstance(ref, dict):
                if ref.get("text"):
                    bibliography.append(ref["text"])

        expected_output = normalize_model_data(citations)

        return {
            "name": f"{test_name}_citation_chunk_{chunk_index}",
            "description": f"Citation detection test for chunk {chunk_index}",
            "input": {
                "main_document": TestDataPaths.main_document(test_name),
                "bibliography": bibliography,  # Supporting documents as bibliography
                "chunk": chunk_content,
            },
            "expected_output": expected_output,
        }


class ClaimTestCaseBuilder:
    """Builds test cases for claim detection."""

    @classmethod
    def build(
        cls,
        test_name: str,
        chunk_index: int,
        chunk_content: str,
        claims: Union[ClaimResponse, ToulminClaimResponse, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build claim test case (no supporting documents needed)."""

        expected_output = normalize_model_data(claims)

        return {
            "name": f"{test_name}_claim_chunk_{chunk_index}",
            "description": f"Claim detection test for chunk {chunk_index}",
            "input": {
                "main_document": TestDataPaths.main_document(test_name),
                "chunk": chunk_content,
            },
            "expected_output": expected_output,
        }


class ReferenceTestCaseBuilder:
    """Builds test cases for reference extraction."""

    @classmethod
    def build(
        cls,
        test_name: str,
        references: List[Union[BibliographyItem, Dict[str, Any]]],
        supporting_files: List[
            Union[BaseModel, Dict[str, Any]]
        ],  # Could be FileDocument models
    ) -> Dict[str, Any]:
        """Build reference extraction test case with supporting documents."""
        # Include supporting documents as they contain the references to extract
        supporting_file_paths = TestDataPaths.supporting_documents(
            test_name, supporting_files
        )

        references_output = [normalize_model_data(ref) for ref in references]

        return {
            "name": f"{test_name}_references",
            "description": "Reference extraction test",
            "input": {
                "main_document": TestDataPaths.main_document(test_name),
                "supporting_documents": supporting_file_paths,  # Supporting documents are crucial
            },
            "expected_output": {"references": references_output},
        }


class SubstantiationTestCaseBuilder:
    """Builds test cases for claim substantiation."""

    @classmethod
    def build_cases(
        cls,
        test_name: str,
        chunk_index: int,
        chunk_content: str,
        claims: Union[ClaimResponse, ToulminClaimResponse, Dict[str, Any]],
        substantiations: List[Union[BaseModel, Dict[str, Any]]],
        supporting_files: List[Union[BaseModel, Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Build substantiation test cases with supporting documents."""
        cases = []

        # Include supporting documents as they're needed to substantiate claims
        supporting_file_paths = TestDataPaths.supporting_documents(
            test_name, supporting_files
        )

        # Create a test case for each substantiation result
        for i, substantiation in enumerate(substantiations):
            expected_output = normalize_model_data(substantiation)

            cases.append(
                {
                    "name": f"{test_name}_substantiation_chunk_{chunk_index}_claim_{i}",
                    "description": f"Claim substantiation test for chunk {chunk_index}, claim {i}",
                    "input": {
                        "main_document": TestDataPaths.main_document(test_name),
                        "supporting_documents": supporting_file_paths,  # Supporting docs are essential
                        "chunk": chunk_content,
                        "claim_index": i,
                    },
                    "expected_output": expected_output,
                }
            )

        return cases
