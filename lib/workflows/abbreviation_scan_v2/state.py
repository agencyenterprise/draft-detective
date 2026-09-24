"""State definitions for abbreviation scan v2 workflow."""

from typing import Annotated, List, Literal, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_serializer

from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    AbbreviationSectionEntry,
    LineRange,
    merge_chunks,
)
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


class AbbreviationScanV2Config(BaseWorkflowConfig):
    """Configuration for abbreviation scan v2 workflow."""

    type: Literal[WorkflowRunType.ABBREVIATION_SCAN_V2] = Field(
        default=WorkflowRunType.ABBREVIATION_SCAN_V2
    )


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
        description="Summary of what was scanned and found.",
    )
    abbreviations_section_ranges: List[LineRange] = Field(
        default_factory=list,
        description="Line ranges of the Abbreviations (or equivalent) section(s).",
    )
    abbreviations_section_entries: List[AbbreviationSectionEntry] = Field(
        default_factory=list,
        description="Entries listed in the Abbreviations section(s).",
    )
    chunks: Annotated[List[AbbreviationChunk], merge_chunks] = Field(
        default_factory=list,
        description="The line-range chunks the document was catalogued in, with per-chunk status.",
    )
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description=(
            "The Abbreviations-section agent's conversation, system prompt included. "
            "Each chunk's conversation is on the chunk itself."
        ),
    )

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        # Checkpointer-hydrated states may contain raw dicts in `messages`
        # because reducers can append items that bypass model construction.
        return [m if isinstance(m, dict) else m.model_dump() for m in messages]
