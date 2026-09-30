"""Published eval logs carry no downloaded source text."""

import json

from inspect_ai.log import EvalSample
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ChatMessageUser, ContentText, ModelOutput

from evals_inspectai.common.log_redaction import REDACTED, redact_sample

TEXT = "Chapter one of a paywalled book that must not be published. " * 20


def _sample() -> EvalSample:
    state = {
        "fetched_references": [
            {"result": {"final_conclusion": "source_found", "file_id": "f1"}, "messages": [{"type": "tool", "name": "read_file_content", "content": TEXT}]}
        ],
        "project_files": [{"id": "f1", "role": "support", "file_name": "book.pdf", "markdown": TEXT, "markdown_tail": TEXT[-200:], "markdown_chars": len(TEXT)}],
    }
    return EvalSample(
        id="book",
        epoch=1,
        input="A reference",
        target="",
        messages=[
            ChatMessageUser(content="Fetch the book"),
            ChatMessageTool(content=[ContentText(text=TEXT)], function="read_file_content", tool_call_id="c1"),
            ChatMessageAssistant(content="Found it."),
        ],
        output=ModelOutput.from_content(model="none", content=json.dumps(state)),
        attachments={"a1": json.dumps(state), "a2": f"[Text of the file]: {TEXT}", "a3": "An unrelated attachment."},
    )


def test_downloaded_text_is_redacted_everywhere_it_appears():
    sample = _sample()
    redact_sample(sample)
    assert "paywalled book" not in sample.model_dump_json()
    output = json.loads(sample.output.completion)
    assert output["project_files"][0]["markdown"] == REDACTED and output["project_files"][0]["markdown_chars"] == len(TEXT)
    assert output["fetched_references"][0]["result"]["final_conclusion"] == "source_found"
    assert sample.messages[1].content == REDACTED and sample.messages[2].text == "Found it."
    assert sample.attachments["a2"] == REDACTED and sample.attachments["a3"] == "An unrelated attachment."
    assert json.loads(sample.attachments["a1"])["fetched_references"][0]["messages"][0]["content"] == REDACTED
