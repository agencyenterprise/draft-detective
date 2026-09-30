"""Strip downloaded source text from an eval log before it is published.

The reference downloader eval scores the file the app kept, so its log carries
that file's text: in the solver's output (``project_files``), in the state
event that records it, in the completeness grader's prompt, and in the
agent's own transcript, where each ``read_file_content`` tool result is an
input to its next model call and a message in the Messages tab. Logs under ``docs/evals/`` are served publicly,
and the downloaded works include paywalled articles and books, so the
published copy is redacted: a workflow state (the output and every state
event's copy of it) keeps each file's name and length and the agents'
conversations, but not the files' text; every ``read_file_content`` result
is replaced by a placeholder wherever it appears; and any other attachment
quoting a kept file (a grader prompt) is replaced too. Scores and explanations are untouched. Rescore from the
unredacted local log, never from the published one.

Run::

    uv run python -m evals_inspectai.common.log_redaction <in.eval> <out.eval>
"""

import json
import sys
from typing import Iterable

from inspect_ai.log import EvalLog, EvalSample, read_eval_log, write_eval_log
from inspect_ai.model import ChatMessageTool

REDACTED = "[downloaded text redacted from the published log]"
# The tool whose results carry a downloaded file's text into the agent's transcript.
READ_TOOL = "read_file_content"
# Slices of a kept file's text that identify an attachment quoting it: long enough to be
# specific to the file, taken at several offsets so a prompt quoting any part is caught.
_PROBE_CHARS = 120
_PROBE_OFFSETS = (0, 500, 2_000, 8_000, 20_000)
_ATTACHMENT = "attachment://"


def _squash(text: str) -> str:
    return " ".join(text.split())


def _kept_texts(output: dict) -> list[str]:
    return [f"{f.get('markdown', '')} {f.get('markdown_tail', '')}" for f in output.get("project_files", [])]


def _probes(texts: Iterable[str]) -> list[str]:
    probes = []
    for text in texts:
        flat = _squash(text)
        probes += [flat[i : i + _PROBE_CHARS] for i in _PROBE_OFFSETS if len(flat) >= i + _PROBE_CHARS]
    return probes


def _attachment_keys(content: object) -> set[str]:
    """Attachment keys a message's content refers to, whether a string or a list of parts."""
    items = content if isinstance(content, list) else [content]
    parts = [c if isinstance(c, str) else getattr(c, "text", "") for c in items]
    return {t.removeprefix(_ATTACHMENT) for t in parts if isinstance(t, str) and t.startswith(_ATTACHMENT)}


def _redact_read_results(sample: EvalSample) -> set[str]:
    """Replace every ``read_file_content`` result in the sample's messages and in its model
    calls' inputs with the placeholder, inline or not, and return the attachment keys they
    referred to."""
    messages = list(sample.messages or [])
    for event in sample.events:
        messages += list(getattr(event, "input", None) or [])
    keys: set[str] = set()
    for message in messages:
        if isinstance(message, ChatMessageTool) and message.function == READ_TOOL:
            keys |= _attachment_keys(message.content)
            message.content = REDACTED
    return keys


def _redact_state(state: dict) -> dict:
    """The workflow state with every kept file's text and every ``read_file_content`` result
    in the agents' saved conversations replaced by the placeholder."""
    for f in state.get("project_files", []):
        if f.get("markdown") or f.get("markdown_tail"):
            f["markdown"], f["markdown_tail"] = REDACTED, ""
    for fetched in state.get("fetched_references", []):
        for message in fetched.get("messages", []) if isinstance(fetched, dict) else []:
            if isinstance(message, dict) and message.get("type") == "tool" and message.get("name") == READ_TOOL:
                message["content"] = REDACTED
    return state


def _redact_json(text: str) -> str:
    """``text`` redacted as a workflow state when it is one; otherwise unchanged."""
    try:
        state = json.loads(text)
    except ValueError:
        return text
    if not isinstance(state, dict) or not ({"project_files", "fetched_references"} & state.keys()):
        return text
    return json.dumps(_redact_state(state))


def redact_sample(sample: EvalSample) -> None:
    """Redact one sample in place (see the module docstring)."""
    try:
        output = json.loads(sample.output.completion)
    except ValueError:
        output = {}
    probes = _probes(_kept_texts(output)) if isinstance(output, dict) else []
    read_results = _redact_read_results(sample)
    for key, value in (sample.attachments or {}).items():
        state = _redact_json(value)
        if state is not value:
            sample.attachments[key] = state
        elif key in read_results or any(p in _squash(value) for p in probes):
            sample.attachments[key] = REDACTED
    completion = _redact_json(sample.output.completion)
    # The output keeps its text in `completion` and, when built from a message, in its choices too.
    for choice in sample.output.choices:
        if isinstance(choice.message.content, str):
            choice.message.content = _redact_json(choice.message.content)
    sample.output.completion = completion


def redact_downloaded_text(log: EvalLog) -> EvalLog:
    for sample in log.samples or []:
        redact_sample(sample)
    return log


if __name__ == "__main__":
    source, target = sys.argv[1], sys.argv[2]
    write_eval_log(redact_downloaded_text(read_eval_log(source)), target)
    print(f"redacted {source} -> {target}")
