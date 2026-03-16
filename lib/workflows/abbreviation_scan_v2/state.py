"""State definitions for abbreviation scan v2 workflow."""

from typing import List, Literal, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_serializer

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class AbbreviationItem(BaseModel):
    """Represents a single occurrence of an abbreviation/acronym in the document."""

    abbr: str = Field(
        description="The abbreviation or acronym, e.g. OUSW, NATO, AI, LLM"
    )
    inline_definition: str = Field(
        description=(
            "The inline definition accompanying this specific occurrence, e.g. "
            "'Office of the Under Secretary of War' for the occurrence "
            "'Office of the Under Secretary of War (OUSW)'. "
            "Empty string if this occurrence has no inline definition immediately accompanying it."
        )
    )
    occurrence_number: int = Field(
        description=(
            "1-based count of how many times this abbreviation has appeared so far in the "
            "document. occurrence_number=1 is the first (and most important) occurrence."
        )
    )
    line_start: int = Field(
        description="1-indexed line number where this occurrence starts in the raw document."
    )
    line_end: int = Field(
        description="1-indexed line number where this occurrence ends in the raw document."
    )
    abbreviations_section_definition: Optional[str] = Field(
        default=None,
        description=(
            "The definition as it appears in the Abbreviations section of the document. "
            "None if the abbreviation is not listed there, or if no Abbreviations section exists."
        ),
    )
    ignored: bool = Field(
        default=False,
        description=(
            "True if this occurrence should be excluded from compliance checks."
        ),
    )
    ignored_reason: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable explanation of why this occurrence is ignored. "
            "Required when ignored=True, None otherwise. "
            'Example: "Defined in heading title — not a valid inline definition."'
        ),
    )


class AbbreviationCheckOutput(BaseModel):
    """Structured response returned by the AbbreviationCheckerAgent."""

    abbreviations: List[AbbreviationItem] = Field(
        description="All abbreviation occurrences found in the document."
    )
    abbreviations_section_found: bool = Field(
        description="Whether an Abbreviations (or equivalent) section was found in the document."
    )
    reasoning: str = Field(
        description="Top-level agent reasoning summarising what was found and how."
    )


class AbbreviationScanV2Config(BaseWorkflowConfig):
    """Configuration for abbreviation scan v2 workflow."""

    type: Literal[WorkflowRunType.ABBREVIATION_SCAN_V2] = Field(
        default=WorkflowRunType.ABBREVIATION_SCAN_V2
    )

    @classmethod
    def requires_api_key(cls) -> bool:
        return True


class AbbreviationScanV2State(BaseWorkflowState):
    """State for abbreviation scan v2 workflow."""

    type: Literal[WorkflowRunType.ABBREVIATION_SCAN_V2] = Field(
        default=WorkflowRunType.ABBREVIATION_SCAN_V2
    )

    config: AbbreviationScanV2Config

    abbreviations: List[AbbreviationItem] = Field(
        default_factory=list,
        description="All abbreviation occurrences found in the document.",
    )
    abbreviations_section_found: bool = Field(
        default=False,
        description="Whether an Abbreviations section was found in the document.",
    )
    reasoning: str = Field(
        default="",
        description="Agent reasoning summarising what was found and how.",
    )
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="LLM conversation messages from the agent invocation.",
    )

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        return [m.model_dump() for m in messages]
