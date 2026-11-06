"""State definitions for abbreviation scan v2 workflow."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lib.workflows.abbreviation_scan_v2.chunk_models import (
    AbbreviationChunk,
    AbbreviationSectionEntry,
    LineRange,
    merge_chunks,
)
from lib.workflows.agent_messages import AgentMessages
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    LocatedQuote,
    WorkflowRunType,
)


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
    abbreviations_section_definition: str | None = Field(
        default=None,
        description=(
            "The definition as it appears in the Abbreviations section of the document. "
            "None if the abbreviation is not listed there, or if no Abbreviations section exists."
        ),
    )
    passage: LocatedQuote | None = Field(
        default=None,
        description=(
            "The words this occurrence's issue is about, located on its line; "
            "None when they could not be pinned down, and on states stored "
            "before passages existed."
        ),
    )
    # Exempt occurrences are no longer catalogued, so these are always False/None on
    # new runs. They stay so states stored before that change still load and score.
    ignored: bool = Field(
        default=False,
        description="Legacy: True if this occurrence was excluded from compliance checks.",
    )
    ignored_reason: str | None = Field(
        default=None,
        description="Legacy: why the occurrence was excluded, when ignored is True.",
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

    abbreviations: list[AbbreviationItem] = Field(
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
    abbreviations_section_ranges: list[LineRange] = Field(
        default_factory=list,
        description="Line ranges of the Abbreviations (or equivalent) section(s).",
    )
    abbreviations_section_entries: list[AbbreviationSectionEntry] = Field(
        default_factory=list,
        description="Entries listed in the Abbreviations section(s).",
    )
    chunks: Annotated[list[AbbreviationChunk], merge_chunks] = Field(
        default_factory=list,
        description="The line-range chunks the document was catalogued in, with per-chunk status.",
    )
    messages: AgentMessages = Field(
        default_factory=list,
        description=(
            "The Abbreviations-section agent's conversation, system prompt included. "
            "Each chunk's conversation is on the chunk itself."
        ),
    )
