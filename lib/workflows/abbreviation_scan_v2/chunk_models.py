"""Models for the chunked extraction stage of abbreviation scan v2.

The document is cut into line-range chunks, each catalogued by its own agent.
Each agent answers only for its own lines, so what it records is deliberately
local: the occurrence number and the Abbreviations-section definition depend on
the whole document and are filled in afterwards, when the chunks are combined.
"""

from enum import Enum
from typing import List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_serializer

from lib.workflows.models import ErrorDetails


class ChunkOccurrence(BaseModel):
    """One abbreviation occurrence, as recorded by a chunk extraction agent."""

    abbr: str = Field(
        description='The abbreviation in its singular base form, e.g. "LLM" not "LLMs".'
    )
    inline_definition: str = Field(
        default="",
        description=(
            "The inline definition accompanying THIS occurrence (the "
            '"Full Name (ABBR)" pattern), or an empty string when none does.'
        ),
    )
    line_start: int = Field(
        description="1-indexed line number in /main.md where the occurrence starts."
    )
    line_end: int = Field(
        description="Line number where the occurrence ends; equal to line_start for a single line."
    )
    ignored: bool = Field(
        default=False,
        description="True when the occurrence is excluded from compliance checks.",
    )
    ignored_reason: Optional[str] = Field(
        default=None,
        description="Brief reason for the exclusion; required when ignored is true, otherwise null.",
    )


class ChunkExtractionResult(BaseModel):
    """Structured response of one chunk extraction agent."""

    occurrences: List[ChunkOccurrence] = Field(
        default_factory=list,
        description="Every abbreviation occurrence in the assigned line range, in reading order.",
    )


class AbbreviationsSectionRange(BaseModel):
    """Where an Abbreviations (or equivalent) section sits, as the agent found it."""

    start_line: int = Field(description="1-indexed line of the section's title.")
    end_line: int = Field(description="1-indexed last line of the section's list.")
    lists_abbreviations: bool = Field(
        description=(
            "True when the section lists abbreviations or acronyms. False for a glossary "
            "that defines only ordinary terms."
        )
    )


class AbbreviationSectionEntry(BaseModel):
    """One entry of the document's Abbreviations (or equivalent) section."""

    abbr: str = Field(description="The abbreviation as listed, e.g. NATO")
    definition: str = Field(
        description="The definition as written in the section, e.g. North Atlantic Treaty Organization"
    )


class LineRange(BaseModel):
    """An inclusive, 1-indexed range of document lines."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    def contains(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line


class ChunkStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    # The response was cut off; the occurrences it finished were salvaged.
    PARTIAL = "partial"
    ERROR = "error"
    # Blank, or inside the Abbreviations section (which is never catalogued).
    SKIPPED = "skipped"


class AbbreviationChunk(BaseModel):
    """One line-range chunk of the document and the outcome of cataloguing it."""

    chunk_index: int
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    status: ChunkStatus = ChunkStatus.PENDING
    skip_reason: Optional[str] = Field(
        default=None,
        description='Why a SKIPPED chunk was not sent to an agent: "abbreviations section" or "blank".',
    )
    occurrences: List[ChunkOccurrence] = Field(default_factory=list)
    error: Optional[str] = None
    error_details: Optional[ErrorDetails] = None
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="The agent's full conversation for this chunk, system prompt included.",
    )

    @property
    def produced_results(self) -> bool:
        return self.status in (ChunkStatus.COMPLETED, ChunkStatus.PARTIAL)

    @field_serializer("messages")
    @classmethod
    def _serialize_messages(cls, messages: List[BaseMessage]) -> list[dict]:
        # Checkpointer-hydrated states may contain raw dicts in `messages`
        # because reducers can append items that bypass model construction.
        return [m if isinstance(m, dict) else m.model_dump() for m in messages]


def merge_chunks(
    existing: List[AbbreviationChunk], new: List[AbbreviationChunk]
) -> List[AbbreviationChunk]:
    """Reducer: merge by chunk_index so each fan-out result replaces its PENDING row."""
    by_index = {chunk.chunk_index: chunk for chunk in existing}
    for chunk in new:
        by_index[chunk.chunk_index] = chunk
    return sorted(by_index.values(), key=lambda chunk: chunk.chunk_index)
