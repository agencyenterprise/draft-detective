"""Per-run tool for collecting abbreviation occurrences from the deep agent.

Occurrences arrive through an ordinary tool call rather than the agent's
terminal structured response. A long document produces hundreds of them, and a
single structured response cannot carry that many: the agent silently truncates
the catalogue to whatever fits, which is how a 111-page document came back
covering only its first 195 lines.

Recording them incrementally removes that ceiling. The agent reports each chunk
as it reads it, so nothing has to be held in context until the end, and the
terminal response shrinks to a short summary.

Mirrors ``lib.workflows.simple_deep_agent.issue_reporting.IssueReporter``: each
agent invocation owns one collector, so concurrent workflow runs cannot share
state.
"""

from threading import Lock
from typing import List, Optional

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from lib.workflows.abbreviation_scan_v2.state import AbbreviationItem

# Occurrences accepted per call. Large enough that a long document needs only a
# handful of calls, small enough that one call's arguments stay well inside the
# model's output budget.
MAX_PER_CALL = 200


class OccurrenceInput(BaseModel):
    """One abbreviation occurrence, as supplied by the agent."""

    abbr: str = Field(description='Abbreviation in singular base form, e.g. "LLM" not "LLMs"')
    inline_definition: str = Field(
        default="",
        description=(
            "The inline definition accompanying THIS occurrence "
            '(the "Full Name (ABBR)" pattern), or an empty string when none does.'
        ),
    )
    occurrence_number: int = Field(
        description="1-based count of how many times this abbreviation has appeared so far"
    )
    line_start: int = Field(description="1-indexed first line of this occurrence")
    line_end: int = Field(description="1-indexed last line; not before line_start")
    abbreviations_section_definition: Optional[str] = Field(
        default=None,
        description=(
            "Definition listed in the Abbreviations section, or null when the "
            "abbreviation is not listed there or no such section exists."
        ),
    )
    ignored: bool = Field(
        default=False,
        description="True when this occurrence is excluded from the compliance checks",
    )
    ignored_reason: Optional[str] = Field(
        default=None, description="Why it is excluded; required when ignored is true"
    )


class AbbreviationReporter:
    """Collect abbreviation occurrences through a tool scoped to one invocation."""

    def __init__(self) -> None:
        self._occurrences: List[AbbreviationItem] = []
        self._seen: set[str] = set()
        self._lock = Lock()
        self.tools = [self._build_record_tool()]

    @property
    def occurrences(self) -> List[AbbreviationItem]:
        """Return a snapshot so callers cannot mutate the collector."""
        with self._lock:
            return list(self._occurrences)

    def _build_record_tool(self) -> BaseTool:
        reporter = self

        @tool()
        def record_abbreviations(occurrences: List[OccurrenceInput]) -> str:
            """Record a batch of abbreviation occurrences found in the document.

            Call this repeatedly as you work through the document — once per
            chunk you read, rather than saving everything for the end. Every
            occurrence must be recorded through this tool; the final response
            carries only a short summary, not the catalogue.

            Args:
                occurrences: The occurrences found so far in this chunk. At most
                    200 per call; split larger batches across several calls.

            Returns:
                A confirmation with the running total, or a correction message
                naming the entries that were rejected.
            """
            if not occurrences:
                return "Nothing recorded: the occurrences list was empty."
            if len(occurrences) > MAX_PER_CALL:
                return (
                    f"Nothing recorded: {len(occurrences)} occurrences exceeds the "
                    f"{MAX_PER_CALL} per-call limit. Split this batch across several calls."
                )

            accepted: List[AbbreviationItem] = []
            rejected: List[str] = []

            for index, candidate in enumerate(occurrences):
                problem = _validate(candidate)
                if problem:
                    rejected.append(f"entry {index + 1} ({candidate.abbr!r}): {problem}")
                    continue
                accepted.append(
                    AbbreviationItem(
                        abbr=candidate.abbr.strip(),
                        inline_definition=candidate.inline_definition,
                        occurrence_number=candidate.occurrence_number,
                        line_start=candidate.line_start,
                        line_end=candidate.line_end,
                        abbreviations_section_definition=candidate.abbreviations_section_definition,
                        ignored=candidate.ignored,
                        ignored_reason=candidate.ignored_reason,
                    )
                )

            with reporter._lock:
                added = 0
                duplicates = 0
                for item in accepted:
                    fingerprint = f"{item.abbr}|{item.occurrence_number}|{item.line_start}"
                    if fingerprint in reporter._seen:
                        duplicates += 1
                        continue
                    reporter._seen.add(fingerprint)
                    reporter._occurrences.append(item)
                    added += 1
                total = len(reporter._occurrences)

            parts = [f"Recorded {added} occurrence(s); {total} total so far."]
            if duplicates:
                parts.append(f"{duplicates} duplicate(s) ignored.")
            if rejected:
                parts.append("Not recorded — " + "; ".join(rejected[:10]))
            return " ".join(parts)

        return record_abbreviations


def _validate(candidate: OccurrenceInput) -> Optional[str]:
    """Return a correction message, or None when the entry is acceptable."""
    if not candidate.abbr.strip():
        return "abbr must not be blank"
    if candidate.occurrence_number < 1:
        return "occurrence_number must be at least 1"
    if candidate.line_start < 1:
        return "line_start must be at least 1"
    if candidate.line_end < candidate.line_start:
        return "line_end must be greater than or equal to line_start"
    if candidate.ignored and not (candidate.ignored_reason or "").strip():
        return "ignored_reason is required when ignored is true"
    return None
