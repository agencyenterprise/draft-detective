from enum import StrEnum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class AdvocacyToneCheckType(StrEnum):
    """Types of advocacy/tone checks."""

    TRIGGER_WORDS = "trigger_words"
    ADVOCACY_LANGUAGE = "advocacy_language"
    SUBJECTIVE_TONE = "subjective_tone"


class ProceduralFlags(BaseModel):
    """Flags from procedural (non-LLM) detection."""

    trigger_words: bool = False
    advocacy_language: bool = False
    subjective_tone: bool = False


class LLMVerificationResult(BaseModel):
    """Result from LLM verification of a procedural flag."""

    confirmed: bool = Field(description="Whether the LLM confirmed the issue")
    explanation: str = Field(description="LLM explanation of the finding")
    word_positions: List[int] = Field(
        default_factory=list,
        description="0-indexed word positions that caused the issue",
    )


class ChunkAdvocacyToneResult(BaseModel):
    """Advocacy and tone analysis result for a single chunk."""

    chunk_index: int = Field(description="Index of the analyzed chunk")
    procedural_flags: ProceduralFlags = Field(
        default_factory=ProceduralFlags,
        description="Flags from procedural detection",
    )
    llm_trigger_words: Optional[LLMVerificationResult] = Field(
        default=None, description="LLM verification for trigger words"
    )
    llm_advocacy_language: Optional[LLMVerificationResult] = Field(
        default=None, description="LLM verification for advocacy language"
    )
    llm_subjective_tone: Optional[LLMVerificationResult] = Field(
        default=None, description="LLM verification for subjective tone"
    )


class AdvocacyToneWorkflowConfig(BaseWorkflowConfig):
    """Configuration for the advocacy and tone workflow."""

    type: Literal[WorkflowRunType.ADVOCACY_TONE] = Field(WorkflowRunType.ADVOCACY_TONE)


class AdvocacyToneState(BaseWorkflowState):
    """State for the advocacy and tone workflow."""

    type: Literal[WorkflowRunType.ADVOCACY_TONE] = Field(WorkflowRunType.ADVOCACY_TONE)
    config: AdvocacyToneWorkflowConfig
    results: List[ChunkAdvocacyToneResult] = Field(default_factory=list)

