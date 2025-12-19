"""Configuration classes for eval package generation."""

from typing import List
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from .file_operations import AGENT_CONFIGS


class PackageConfig:
    """Configuration for package generation to eliminate duplication."""
    
    def __init__(
        self,
        selected_agents: List[str] = None,
        target_chunks: List[AnalyzedChunk] = None
    ):
        self.selected_agents = selected_agents or list(AGENT_CONFIGS.keys())
        self.target_chunks = target_chunks  # None = all chunks
    
    @property
    def filename_suffix(self) -> str:
        """Generate appropriate filename suffix."""
        if self.is_chunk_mode:
            return f"_chunk_{self.chunk_index}_eval_package.zip"
        return "_eval_package.zip"
    
    @property
    def is_chunk_mode(self) -> bool:
        """Check if this is chunk-specific generation."""
        return self.target_chunks is not None and len(self.target_chunks) == 1
    
    @property
    def chunk_index(self) -> int:
        """Get the chunk index when in chunk mode."""
        if self.is_chunk_mode:
            return self.target_chunks[0].chunk_index
        return None
    
    @property
    def use_optimized_files(self) -> bool:
        """Check if we should use optimized file saving."""
        all_agents = set(AGENT_CONFIGS.keys())
        selected_agents_set = set(self.selected_agents)
        return selected_agents_set != all_agents  # Optimize when not using all agents
