"""OpenAI's internal file-citation tokens, turned into readable references.

When a gpt-5.x model has read a file it tends to cite it the way it was trained
to: ``\\ue200filecite\\ue202<path>\\ue202L3-L9\\ue201``, three private-use
characters framing a payload. Behind OpenAI's hosted file search the API turns
that into an annotation; with files read through our own tools the tokens reach
the text as they are, and the page shows them as boxes.

The payload is still useful (which file, which lines), so it becomes a plain
reference such as ``(draft.md, lines 3–9)``. Any other framed payload is dropped.

Streaming complicates this only slightly: a marker spans several tokens, so
``CitationFilter`` holds text back from an opening character until the closing
one arrives, and ``flush`` releases whatever is left when the message ends.
"""

import re

START, SEPARATOR, END = "", "", ""

_LINE_RANGE = re.compile(r"L(\d+)(?:-L?(\d+))?")


def render_citation(payload: str) -> str:
    """The text a framed citation payload becomes; empty for anything unknown."""

    parts = payload.split(SEPARATOR)
    if len(parts) < 2 or parts[0] != "filecite" or not parts[1]:
        return ""
    name = parts[1].rsplit("/", 1)[-1]
    if len(parts) < 3:
        return f"({name})"
    match = _LINE_RANGE.fullmatch(parts[2].strip())
    if match is None:
        return f"({name})"
    first, last = match.group(1), match.group(2)
    lines = f"line {first}" if last is None or last == first else f"lines {first}–{last}"
    return f"({name}, {lines})"


class CitationFilter:
    """Rewrites citation markers in a text stream, buffering across chunks."""

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, delta: str) -> str:
        text = self._pending + delta
        self._pending = ""
        out: list[str] = []
        while text:
            start = text.find(START)
            if start < 0:
                out.append(text)
                break
            out.append(text[:start])
            rest = text[start + 1 :]
            end = rest.find(END)
            if end < 0:
                # The marker is not complete yet: hold it back for the next chunk.
                self._pending = text[start:]
                break
            out.append(render_citation(rest[:end]))
            text = rest[end + 1 :]
        return "".join(out)

    def flush(self) -> str:
        """Whatever was held back, rendered as well as an unterminated marker allows."""

        pending, self._pending = self._pending, ""
        if not pending:
            return ""
        return render_citation(pending[1:].rstrip(END))


def render_citations(text: str) -> str:
    """The non-streaming form, for text that is already complete."""

    citations = CitationFilter()
    return citations.feed(text) + citations.flush()
