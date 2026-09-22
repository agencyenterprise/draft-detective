"""Per-run tools for collecting document issues from a deep agent.

Issue reporting is an ordinary tool interaction rather than the agent's terminal
structured response. Each agent invocation owns one collector, so calls from
concurrent workflow runs cannot share state. The agent explicitly completes the
report by writing `/report.md`; zero issue-tool calls means no issues were found.

Proposed edits are opt-in per workflow. A collector built with
``propose_edits=True`` hands the agent a `report_issue` tool that takes an
`edits` argument and locates every quote in the document before the issue is
recorded, so a stored edit always points at real lines. Otherwise the agent
gets the plain tool, with no mention of edits at all, so the option costs no
context for workflows that do not use it.
"""

from threading import Lock
from typing import Any, List, Literal, Optional, Union

from deepagents.backends.utils import file_data_to_string
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from lib.agents.tools.view_image import redact_image_blocks
from lib.services.markdown_text import (
    rendered_replacement_in_context,
    rendered_span,
)
from lib.services.text_location import locate_in_paragraph
from lib.workflows.models import ProposedEdit
from lib.workflows.simple_deep_agent.agent_types import DeepAgentRun, IssueItem
from lib.workflows.simple_deep_agent.edit_anchoring import (
    document_lines,
    find_quote_lines,
    normalize_whitespace,
    range_excerpt,
)


class ProposedEditInput(BaseModel):
    """One mechanical replacement an agent proposes alongside an issue."""

    original_text: str = Field(
        description=(
            "The text to replace, quoted verbatim from the document within the "
            "issue's line range. Keep it short: a phrase or a single sentence, "
            "always within one line of the document."
        )
    )
    replacement_text: str = Field(
        description=(
            "The text that takes its place. Use an empty string to delete the "
            "quoted text; to insert, repeat the quoted text with the addition."
        )
    )
    rationale: str = Field(
        description="One short sentence on why this replacement fixes the issue."
    )


class _EditResolution(BaseModel):
    """Outcome of checking an issue's proposed edits against the document."""

    edits: List[ProposedEdit] = Field(default_factory=list)
    rejection: Optional[str] = Field(
        default=None,
        description="Set when the whole issue must be rejected so the agent can retry.",
    )


class IssueReporter:
    """Collect validated issues through tools scoped to one agent invocation.

    With ``propose_edits`` the tool accepts proposed edits, which requires
    ``document_text`` (the markdown under review) to check the quotes against.
    """

    def __init__(
        self, propose_edits: bool = False, document_text: Optional[str] = None
    ) -> None:
        if propose_edits and document_text is None:
            raise ValueError("Proposed edits need the document text to check against.")
        self._lines: List[str] = document_lines(document_text or "")
        self._issues: List[IssueItem] = []
        self._issue_ids: dict[str, str] = {}
        self._lock = Lock()
        build = self._build_edits_tool if propose_edits else self._build_report_tool
        self.tools = [build()]

    @property
    def issues(self) -> List[IssueItem]:
        """Return a snapshot so callers cannot mutate the collector."""
        with self._lock:
            return list(self._issues)

    def _record(
        self,
        title: str,
        description: str,
        severity: Literal["none", "low", "medium", "high"],
        start_line: int,
        end_line: int,
        long_description: Optional[str],
        suggested_action: Optional[str],
        edits: Optional[List[ProposedEditInput]] = None,
    ) -> str:
        """Validate and record one issue; shared by both tool variants."""
        if not title.strip():
            return "Issue was not recorded: title must not be blank."
        if not description.strip():
            return "Issue was not recorded: description must not be blank."
        if start_line < 1:
            return "Issue was not recorded: start_line must be at least 1."
        if end_line < start_line:
            return (
                "Issue was not recorded: end_line must be greater than or "
                "equal to start_line."
            )

        resolution = self._resolve_edits(edits, start_line, end_line)
        if resolution.rejection is not None:
            return f"Issue was not recorded: {resolution.rejection}"

        issue = IssueItem(
            title=title,
            description=description,
            severity=severity,
            start_line=start_line,
            end_line=end_line,
            long_description=long_description,
            suggested_action=suggested_action,
            edits=resolution.edits,
        )
        # Edits are excluded so the fingerprint identifies the finding, not
        # its fix: the same issue reported twice is a duplicate whether or
        # not the second call carried edits.
        fingerprint = issue.model_dump_json(exclude_none=False, exclude={"edits"})

        with self._lock:
            existing_id = self._issue_ids.get(fingerprint)
            if existing_id is not None:
                return f"Issue already recorded as {existing_id}; duplicate ignored."

            issue_id = f"issue-{len(self._issues) + 1}"
            self._issues.append(issue)
            self._issue_ids[fingerprint] = issue_id
            return f"Recorded {issue_id}: {issue.title}"

    def _resolve_edits(
        self, edits: Optional[List[ProposedEditInput]], start_line: int, end_line: int
    ) -> _EditResolution:
        """Locate every proposed edit in the document, or explain what is wrong."""
        if not edits:
            return _EditResolution()

        resolved: List[ProposedEdit] = []
        for position, edit in enumerate(edits, start=1):
            outcome = self._resolve_edit(edit, position, start_line, end_line)
            if isinstance(outcome, str):
                return _EditResolution(rejection=outcome)
            resolved.append(outcome)
        return _EditResolution(edits=resolved)

    def _resolve_edit(
        self,
        edit: ProposedEditInput,
        position: int,
        start_line: int,
        end_line: int,
    ) -> Union[ProposedEdit, str]:
        """Turn one proposed edit into a located edit, or a corrective message."""
        lines = self._lines
        label = f"edit {position}"
        if not edit.original_text.strip():
            return f"{label}: original_text must not be blank."
        if edit.replacement_text == edit.original_text:
            return (
                f"{label}: replacement_text is identical to original_text, so the "
                "edit would change nothing."
            )

        # The app renders `$$...$$` as MathML and Word holds an equation as
        # OMML with no delimiters, so neither surface has characters an edit
        # could be placed on. Single-dollar text is not math in the app
        # (`singleDollarTextMath: false`), so `$5 million` is ordinary prose.
        if "$$" in edit.original_text or "$$" in edit.replacement_text:
            return (
                f"{label}: original_text and replacement_text must not contain "
                "display math (`$$...$$`); the export cannot place equations."
            )

        matches = find_quote_lines(lines, start_line, end_line, edit.original_text)
        if not matches:
            return (
                f"{label}: original_text was not found on any single line of lines "
                f"{start_line}-{end_line}. Quote it verbatim from one line of the "
                f"document. Lines {start_line}-{end_line} read: "
                f"{range_excerpt(lines, start_line, end_line)!r}"
            )
        if len(matches) > 1:
            return (
                f"{label}: original_text appears {len(matches)} times in lines "
                f"{start_line}-{end_line}. Quote a longer span that appears only "
                "once (up to the whole line) and make the replacement inside it."
            )
        line = matches[0]

        # The rendered form is settled here, once, and stored with the edit:
        # the in-app highlight and the DOCX redline both look for the
        # characters the reader sees, and neither should have to re-derive
        # them from the markdown.
        spans = locate_in_paragraph(
            lines[line - 1], normalize_whitespace(edit.original_text)
        )
        rendered = (
            rendered_span(lines[line - 1], spans[0][0], spans[0][1])
            if len(spans) == 1
            else None
        )
        if rendered is None:
            return (
                f"{label}: original_text must start and end on plain text, not "
                "inside a link address or a formatting marker. Quote whole "
                "words from the line, including any markup that surrounds them."
            )

        # Rendered where the quote sat, not on its own: the quote may open or
        # close inside formatting that carries on around it, and so does the
        # replacement that takes its place.
        replacement = rendered_replacement_in_context(
            lines[line - 1], spans[0][0], spans[0][1], edit.replacement_text
        )
        if replacement is None:
            return (
                f"{label}: replacement_text cannot be placed where "
                "original_text sits without breaking the surrounding "
                "formatting; quote the whole formatted span instead."
            )

        return ProposedEdit(
            original_text=edit.original_text,
            replacement_text=edit.replacement_text,
            rationale=edit.rationale,
            start_line=line,
            end_line=line,
            display_text=rendered.display_text,
            display_occurrence=rendered.display_occurrence,
            display_replacement=replacement,
        )

    def _build_report_tool(self) -> BaseTool:
        reporter = self

        @tool()
        def report_issue(
            title: str,
            description: str,
            severity: Literal["none", "low", "medium", "high"],
            start_line: int,
            end_line: int,
            long_description: Optional[str] = None,
            suggested_action: Optional[str] = None,
        ) -> str:
            """Report one verified issue in the document under review.

            Call this exactly once for each genuine issue after checking it
            against the document under review. Do not call it for passing rules
            unless the workflow explicitly requests an informational issue with
            severity `none`. If a call is rejected, correct the arguments and
            try again.

            Args:
                title: Short, specific issue title.
                description: Concise markdown explanation grounded in the document.
                severity: Impact level: none, low, medium, or high.
                start_line: 1-indexed first relevant line in the document.
                end_line: 1-indexed last relevant line; not before start_line.
                long_description: Optional extended markdown detail.
                suggested_action: Optional direct recommendation for the author.

            Returns:
                A confirmation containing the recorded issue identifier, or a
                correction message when the issue was not recorded.
            """
            return reporter._record(
                title,
                description,
                severity,
                start_line,
                end_line,
                long_description,
                suggested_action,
            )

        return report_issue

    def _build_edits_tool(self) -> BaseTool:
        reporter = self

        @tool()
        def report_issue(
            title: str,
            description: str,
            severity: Literal["none", "low", "medium", "high"],
            start_line: int,
            end_line: int,
            long_description: Optional[str] = None,
            suggested_action: Optional[str] = None,
            edits: Optional[List[ProposedEditInput]] = None,
        ) -> str:
            """Report one verified issue in the document under review.

            Call this exactly once for each genuine issue after checking it
            against the document under review. Do not call it for passing rules
            unless the workflow explicitly requests an informational issue with
            severity `none`. If a call is rejected, correct the arguments and
            try again.

            Args:
                title: Short, specific issue title.
                description: Concise markdown explanation grounded in the document.
                severity: Impact level: none, low, medium, or high.
                start_line: 1-indexed first relevant line in the document.
                end_line: 1-indexed last relevant line; not before start_line.
                long_description: Optional extended markdown detail.
                suggested_action: Optional direct recommendation for the author.
                edits: Optional list of mechanical text replacements that resolve
                    this issue, each with `original_text` (the text to replace,
                    quoted verbatim from the document under review and inside
                    this issue's line range), `replacement_text` (what takes its
                    place; empty string to delete, and to insert repeat the
                    quoted text with the addition), and a one-sentence
                    `rationale`. `original_text` must appear exactly once in the
                    line range; if it repeats, quote a longer span (up to the
                    whole line). Propose an edit only when the fix is fully determined
                    by the document text plus this finding. Never propose one
                    that needs a fact or a sentence you would have to invent:
                    leave those to `suggested_action` alone. Keep each
                    `original_text` short (a phrase or one sentence) and within
                    one line of the document -- it must not cross a line break.
                    Set `suggested_action` as well; an edit is its structured
                    form, not its replacement.

            Returns:
                A confirmation containing the recorded issue identifier, or a
                correction message when the issue was not recorded.
            """
            return reporter._record(
                title,
                description,
                severity,
                start_line,
                end_line,
                long_description,
                suggested_action,
                edits,
            )

        return report_issue


def collect_deep_agent_run(
    result: dict[str, Any], issue_reporter: Optional[IssueReporter] = None
) -> DeepAgentRun:
    """Convert a raw DeepAgents result and optional collector into one run."""
    return DeepAgentRun(
        files={
            path: file_data_to_string(data)
            for path, data in (result.get("files") or {}).items()
        },
        reported_issues=issue_reporter.issues if issue_reporter else [],
        # Viewed images are base64 in the tool results; keep the transcript
        # readable and the persisted state small.
        messages=redact_image_blocks(result["messages"]),
    )
