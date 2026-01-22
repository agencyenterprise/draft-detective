"""Main eval test generator service using modular components."""

import io
import zipfile
import logging
from typing import Dict, List, Optional, cast

from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lib.models.bibliography_item import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.chunk_utils import AnalyzedChunk, build_analyzed_chunks
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_file_matching.state import ReferenceFileMatchingState
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type

from .test_case_builders import (
    CitationTestCaseBuilder,
    ClaimTestCaseBuilder,
    ReferenceTestCaseBuilder,
)
from .file_operations import (
    DataFileManager,
    YamlFileWriter,
    ReadmeGenerator,
)
from .requirements_analyzer import RequirementsAnalyzer
from .package_config import PackageConfig

__all__ = ["eval_test_generator"]

logger = logging.getLogger(__name__)


class EvalPackageData(BaseModel):
    """Data required for eval package generation, collected from workflow states."""

    file: FileDocument
    supporting_files: List[FileDocument] = Field(default_factory=list)
    references: List[BibliographyItem] = Field(default_factory=list)
    chunks: List[AnalyzedChunk] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class EvalPackageRequest(BaseModel):
    """Request model for generating eval packages."""

    project_id: str = Field(description="The project ID to generate eval package for")
    test_name: str = Field(default="generated_test")
    description: str = Field(default="Generated from frontend analysis")


class ChunkEvalPackageRequest(BaseModel):
    """Request model for generating chunk-specific eval packages."""

    project_id: str = Field(description="The project ID to generate eval package for")
    chunk_index: int
    selected_agents: List[str]
    test_name: str = Field(default="generated_chunk_test")
    description: str = Field(default="Generated from chunk analysis")


async def build_eval_package_data(project_id: str) -> EvalPackageData:
    """
    Build eval package data from workflow states for a project.

    Args:
        project_id: The project ID to fetch workflow states for

    Returns:
        EvalPackageData with file, supporting_files, references, and chunks
    """
    from lib.services.workflow_runs import get_project_workflow_runs

    # Get all workflow runs including internal ones
    workflow_runs = await get_project_workflow_runs(project_id, include_internal=True)
    existing_states: List[WorkflowState] = [
        run.state for run in workflow_runs if run.state is not None
    ]

    # Get document processing state for file info
    doc_processing_state_raw = get_state_by_type(
        WorkflowRunType.DOCUMENT_PROCESSING, existing_states
    )
    if doc_processing_state_raw is None:
        raise ValueError(f"No document processing state found for project {project_id}")

    doc_processing_state = cast(DocumentProcessingState, doc_processing_state_raw)

    # Build references from extraction and file matching states
    references: List[BibliographyItem] = []
    ref_extraction_state_raw = get_state_by_type(
        WorkflowRunType.REFERENCE_EXTRACTION, existing_states
    )
    if ref_extraction_state_raw is not None:
        ref_extraction_state = cast(ReferenceExtractionState, ref_extraction_state_raw)
        extracted_refs = ref_extraction_state.extracted_references

        # Try to get file matching info
        ref_to_file: dict[str, str] = {}
        file_matching_state_raw = get_state_by_type(
            WorkflowRunType.REFERENCE_FILE_MATCHING, existing_states
        )
        if file_matching_state_raw is not None:
            file_matching_state = cast(
                ReferenceFileMatchingState, file_matching_state_raw
            )
            for match in file_matching_state.matches:
                ref_to_file[match.reference_id] = match.file_id

        # Build file lookup for names and indices
        supporting_files = doc_processing_state.supporting_files or []
        file_names = {f.file_id: f.file_name for f in supporting_files}
        file_indices = {f.file_id: idx + 1 for idx, f in enumerate(supporting_files)}

        # Compose BibliographyItems
        for ref in extracted_refs:
            file_id = ref_to_file.get(ref.id)
            has_match = file_id is not None
            references.append(
                BibliographyItem(
                    text=ref.text,
                    has_associated_supporting_document=has_match,
                    index_of_associated_supporting_document=(
                        file_indices.get(file_id, -1) if file_id else -1
                    ),
                    name_of_associated_supporting_document=(
                        file_names.get(file_id, "") if file_id else ""
                    ),
                    file_id=file_id,
                )
            )

    # Build analyzed chunks from workflow states
    chunks = build_analyzed_chunks(existing_states)

    return EvalPackageData(
        file=doc_processing_state.file,
        supporting_files=doc_processing_state.supporting_files or [],
        references=references,
        chunks=chunks,
    )


class EvalTestGenerator:
    """Service for generating evaluation test packages from analysis results."""

    def __init__(self):
        pass

    async def generate_package(
        self, project_id: str, test_name: str, description: str
    ) -> StreamingResponse:
        """
        Generate complete eval test package as downloadable zip.

        Args:
            project_id: The project ID to generate eval package for
            test_name: Name for the test case
            description: Description of the test case

        Returns:
            StreamingResponse with ZIP file
        """
        data = await build_eval_package_data(project_id)
        config = PackageConfig()  # Default: all agents, all chunks
        return self._generate_package_core(data, test_name, description, config)

    async def generate_chunk_package(
        self,
        project_id: str,
        chunk_index: int,
        selected_agents: List[str],
        test_name: str,
        description: str,
    ) -> StreamingResponse:
        """
        Generate eval test package for a specific chunk with selected agents.
        Only includes necessary files based on agent requirements.

        Args:
            project_id: The project ID to generate eval package for
            chunk_index: Index of the specific chunk to generate tests for
            selected_agents: List of agent IDs to generate tests for
            test_name: Name for the test case
            description: Description of the test case

        Returns:
            StreamingResponse with optimized ZIP file
        """
        data = await build_eval_package_data(project_id)

        # Get the specific chunk
        if chunk_index >= len(data.chunks):
            raise ValueError(f"Chunk index {chunk_index} not found in results")

        target_chunk = data.chunks[chunk_index]
        config = PackageConfig(
            selected_agents=selected_agents, target_chunks=[target_chunk]
        )
        return self._generate_package_core(data, test_name, description, config)

    def _generate_package_core(
        self,
        data: EvalPackageData,
        test_name: str,
        description: str,
        config: PackageConfig,
    ) -> StreamingResponse:
        """
        Unified core package generation method that handles both full and chunk packages.

        Args:
            data: EvalPackageData with file, supporting_files, references, chunks
            test_name: Name for the test case
            description: Description of the test case
            config: PackageConfig object defining generation parameters

        Returns:
            StreamingResponse with ZIP file
        """
        # Log generation details
        if config.is_chunk_mode:
            logger.info(
                f"Generating chunk eval package '{test_name}' for chunk {config.chunk_index} with agents: {config.selected_agents}"
            )
        else:
            logger.info(
                f"Generating eval package '{test_name}' with {len(data.chunks)} chunks"
            )
            logger.info(f"References count: {len(data.references)}")
            logger.info(f"Supporting files count: {len(data.supporting_files)}")

        # Create in-memory zip file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Save data files (optimized or full)
            if config.use_optimized_files:
                DataFileManager.save_required_data_files(
                    zip_file, data, test_name, config.selected_agents
                )
            else:
                DataFileManager.save_data_files(zip_file, data, test_name)

            # 2. Generate test cases based on configuration
            test_cases = self._extract_unified_test_cases(
                data, test_name, config.selected_agents, config.target_chunks
            )

            # 3. Write YAML files for selected agents
            YamlFileWriter.write_selective_yaml_files(
                zip_file, test_cases, test_name, description, config.selected_agents
            )

            # 4. Add appropriate README
            if config.is_chunk_mode:
                ReadmeGenerator.add_chunk_readme(
                    zip_file,
                    test_name,
                    description,
                    config.chunk_index,
                    config.selected_agents,
                )
            else:
                ReadmeGenerator.add_readme(zip_file, test_name, description)

        zip_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={test_name}{config.filename_suffix}"
            },
        )

    def _extract_unified_test_cases(
        self,
        data: EvalPackageData,
        test_name: str,
        selected_agents: Optional[List[str]] = None,
        target_chunks: Optional[List[AnalyzedChunk]] = None,
    ) -> Dict[str, List[Dict]]:
        """Unified test case extraction for chunks with optional agent filtering."""
        chunks = target_chunks if target_chunks else data.chunks
        all_agents = selected_agents is None  # If no agents specified, include all

        citation_cases = []
        claim_cases = []
        ref_cases = []
        substantiation_cases = []

        # Process chunks
        for chunk in chunks:
            chunk_index = chunk.chunk_index
            chunk_content = chunk.content
            citations = chunk.citations or {}
            claims = chunk.claims or {}

            # Process each agent type using unified logic
            agent_data = {
                "citations": citations,
                "claims": claims,
            }

            for agent_type, agent_data_item in agent_data.items():
                if self._should_include_agent(
                    agent_type, agent_data_item, all_agents, selected_agents
                ):
                    self._build_test_cases_for_agent(
                        agent_type,
                        test_name,
                        chunk_index,
                        chunk_content,
                        citations,
                        claims,
                        data,
                        citation_cases,
                        claim_cases,
                        substantiation_cases,
                    )

        # Reference extractor works on full document, not individual chunks
        if self._should_include_agent(
            "references", data.references, all_agents, selected_agents
        ):
            ref_cases.append(
                ReferenceTestCaseBuilder.build(
                    test_name, data.references, data.supporting_files
                )
            )

        return {
            "citations": citation_cases,
            "claims": claim_cases,
            "references": ref_cases,
            "substantiation": substantiation_cases,
        }

    def _should_include_agent(
        self,
        agent_type: str,
        data,
        all_agents: bool,
        selected_agents: Optional[List[str]],
    ) -> bool:
        """Determine if an agent should be included based on data availability and selection."""
        if all_agents:
            # For all agents mode, check if data is valid
            return RequirementsAnalyzer.has_valid_items(data, agent_type)

        if selected_agents:
            # For selected agents mode, check both selection and data validity
            return RequirementsAnalyzer.should_generate_agent_tests(
                agent_type, selected_agents, data
            )

        return False

    def _build_test_cases_for_agent(
        self,
        agent_type: str,
        test_name: str,
        chunk_index: int,
        chunk_content: str,
        citations,
        claims,
        data: EvalPackageData,
        citation_cases: List[Dict],
        claim_cases: List[Dict],
        substantiation_cases: List[Dict],
    ):
        """Build test cases for a specific agent type."""
        if agent_type == "citations":
            citation_cases.append(
                CitationTestCaseBuilder.build(
                    test_name, chunk_index, chunk_content, citations, data.references
                )
            )
        elif agent_type == "claims":
            claim_cases.append(
                ClaimTestCaseBuilder.build(
                    test_name, chunk_index, chunk_content, claims
                )
            )
        # Note: substantiation test cases require additional workflow state (ClaimReferenceValidation)
        # which would need to be fetched separately if needed


eval_test_generator = EvalTestGenerator()
