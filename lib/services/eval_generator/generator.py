"""Main eval test generator service using modular components."""

import io
import zipfile
import logging
from typing import Dict, List
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lib.workflows.claim_substantiation.state import AnalyzedChunk, ClaimSubstantiatorState

from .test_case_builders import (
    CitationTestCaseBuilder,
    ClaimTestCaseBuilder, 
    ReferenceTestCaseBuilder,
    SubstantiationTestCaseBuilder,
    TestDataPaths,
    normalize_model_data
)
from .file_operations import DataFileManager, YamlFileWriter, ReadmeGenerator, AGENT_CONFIGS
from .requirements_analyzer import RequirementsAnalyzer
from .package_config import PackageConfig

__all__ = ["eval_test_generator"]

logger = logging.getLogger(__name__)

class EvalPackageRequest(BaseModel):
    results: ClaimSubstantiatorState
    test_name: str = Field(default="generated_test")
    description: str = Field(default="Generated from frontend analysis")

class ChunkEvalPackageRequest(BaseModel):
    results: ClaimSubstantiatorState
    chunk_index: int
    selected_agents: List[str]
    test_name: str = Field(default="generated_chunk_test")
    description: str = Field(default="Generated from chunk analysis")

class EvalTestGenerator:
    """Service for generating evaluation test packages from analysis results."""

    def __init__(self):
        pass

    def generate_package(
        self, 
        results: ClaimSubstantiatorState, 
        test_name: str, 
        description: str
    ) -> StreamingResponse:
        """
        Generate complete eval test package as downloadable zip.
        
        Args:
            results: ClaimSubstantiatorState object with analysis results
            test_name: Name for the test case
            description: Description of the test case
            
        Returns:
            StreamingResponse with ZIP file
        """
        config = PackageConfig()  # Default: all agents, all chunks
        return self._generate_package_core(results, test_name, description, config)

    def generate_chunk_package(
        self, 
        results: ClaimSubstantiatorState, 
        chunk_index: int,
        selected_agents: List[str],
        test_name: str, 
        description: str
    ) -> StreamingResponse:
        """
        Generate eval test package for a specific chunk with selected agents.
        Only includes necessary files based on agent requirements.
        
        Args:
            results: ClaimSubstantiatorState object with full analysis results
            chunk_index: Index of the specific chunk to generate tests for
            selected_agents: List of agent IDs to generate tests for
            test_name: Name for the test case
            description: Description of the test case
            
        Returns:
            StreamingResponse with optimized ZIP file
        """
        # Get the specific chunk
        chunks = results.chunks
        if chunk_index >= len(chunks):
            raise ValueError(f"Chunk index {chunk_index} not found in results")
        
        target_chunk = chunks[chunk_index]
        config = PackageConfig(
            selected_agents=selected_agents,
            target_chunks=[target_chunk]
        )
        return self._generate_package_core(results, test_name, description, config)

    def _generate_package_core(
        self,
        results: ClaimSubstantiatorState,
        test_name: str,
        description: str,
        config: PackageConfig
    ) -> StreamingResponse:
        """
        Unified core package generation method that handles both full and chunk packages.
        
        Args:
            results: ClaimSubstantiatorState object with analysis results
            test_name: Name for the test case
            description: Description of the test case
            config: PackageConfig object defining generation parameters
            
        Returns:
            StreamingResponse with ZIP file
        """
        # Log generation details
        if config.is_chunk_mode:
            logger.info(f"Generating chunk eval package '{test_name}' for chunk {config.chunk_index} with agents: {config.selected_agents}")
        else:
            logger.info(f"Generating eval package '{test_name}' with {len(results.chunks)} chunks")
            logger.info(f"References count: {len(results.references)}")
            logger.info(f"Supporting files count: {len(results.supporting_files)}")
        
        # Create in-memory zip file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Save data files (optimized or full)
            if config.use_optimized_files:
                DataFileManager.save_required_data_files(zip_file, results, test_name, config.selected_agents)
            else:
                DataFileManager.save_data_files(zip_file, results, test_name)
            
            # 2. Generate test cases based on configuration
            test_cases = self._extract_unified_test_cases(
                results, test_name, config.selected_agents, config.target_chunks
            )
            
            # 3. Write YAML files for selected agents
            YamlFileWriter.write_selective_yaml_files(
                zip_file, test_cases, test_name, description, config.selected_agents
            )
            
            # 4. Add appropriate README
            if config.is_chunk_mode:
                ReadmeGenerator.add_chunk_readme(
                    zip_file, test_name, description, config.chunk_index, config.selected_agents
                )
            else:
                ReadmeGenerator.add_readme(zip_file, test_name, description)
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={test_name}{config.filename_suffix}"}
        )

    def _extract_unified_test_cases(
        self, 
        results: ClaimSubstantiatorState,
        test_name: str,
        selected_agents: List[str] = None,
        target_chunks: List[AnalyzedChunk] = None
    ) -> Dict[str, List[Dict]]:
        """Unified test case extraction for chunks with optional agent filtering."""
        chunks = target_chunks if target_chunks else results.chunks
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
            substantiations = chunk.substantiations
            
            # Process each agent type using unified logic
            agent_data = {
                "citations": citations,
                "claims": claims,
                "substantiation": substantiations
            }
            
            for agent_type, data in agent_data.items():
                if self._should_include_agent(agent_type, data, all_agents, selected_agents):
                    self._build_test_cases_for_agent(
                        agent_type, test_name, chunk_index, chunk_content, 
                        citations, claims, substantiations, results,
                        citation_cases, claim_cases, substantiation_cases
                    )
        
        # Reference extractor works on full document, not individual chunks
        if self._should_include_agent("references", results.references, all_agents, selected_agents):
            ref_cases.append(ReferenceTestCaseBuilder.build(test_name, results.references, results.supporting_files))
        
        return {
            "citations": citation_cases,
            "claims": claim_cases,
            "references": ref_cases,
            "substantiation": substantiation_cases
        }

    def _should_include_agent(self, agent_type: str, data, all_agents: bool, selected_agents: List[str]) -> bool:
        """Determine if an agent should be included based on data availability and selection."""
        if all_agents:
            # For all agents mode, check if data is valid
            return RequirementsAnalyzer.has_valid_items(data, agent_type)
        
        if selected_agents:
            # For selected agents mode, check both selection and data validity
            return RequirementsAnalyzer.should_generate_agent_tests(agent_type, selected_agents, data)
        
        return False

    def _build_test_cases_for_agent(
        self, 
        agent_type: str, 
        test_name: str, 
        chunk_index: int, 
        chunk_content: str,
        citations, 
        claims, 
        substantiations, 
        results: ClaimSubstantiatorState,
        citation_cases: List[Dict], 
        claim_cases: List[Dict], 
        substantiation_cases: List[Dict]
    ):
        """Build test cases for a specific agent type."""
        if agent_type == "citations":
            citation_cases.append(CitationTestCaseBuilder.build(
                test_name, chunk_index, chunk_content, citations, results.references
            ))
        elif agent_type == "claims":
            claim_cases.append(ClaimTestCaseBuilder.build(
                test_name, chunk_index, chunk_content, claims
            ))
        elif agent_type == "substantiation":
            substantiation_cases.extend(SubstantiationTestCaseBuilder.build_cases(
                test_name, chunk_index, chunk_content, claims, substantiations, results.supporting_files
            ))


eval_test_generator = EvalTestGenerator()