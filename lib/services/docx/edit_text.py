"""What a proposed edit's markdown says about whether Word can redline it.

The rendered form of an edit -- the characters the page and the DOCX actually
show -- is settled once at report time by `lib.services.markdown_text` and
stored on the row. What is left here reads the *raw* markdown for the few
questions only the source can answer: whether the edit sits in a table, and
whether its replacement carries a character Word cannot take as a tracked
insertion.

Pure functions only -- no document loading -- so the rules can be unit-tested
on plain strings.
"""

from typing import Optional

FIRST_LINE_ONLY = "the replacement spans more than one paragraph"
NO_TABS = "the replacement contains a tab"
LINK_DESTINATION_CHANGED = (
    "it changes a link destination, which the export cannot write"
)


def is_table_row(line: str) -> bool:
    """Whether a markdown line is a table row, its header or its delimiter.

    MarkItDown writes every row with a leading pipe (``| Metric | Value |``),
    which is the form the converted documents carry. The pipe-less GFM variant
    (``Metric | Value |``) is covered too: a line that ends on a pipe and
    carries at least two of them is a row, and prose does not end on a pipe. A
    single pipe inside a sentence stays prose.

    It matters because a table is Word cells, never one of the body paragraphs
    the line-range mapper indexes, and a row can repeat its section's prose
    word for word -- so a row has to be recognised as one before its text is
    compared to any paragraph.
    """
    stripped = line.strip()
    if stripped.startswith("|"):
        return True
    return stripped.endswith("|") and stripped.count("|") >= 2


def unsupported_replacement_reason(text: str) -> Optional[str]:
    """Why the replacement cannot become a redline, or None when it can.

    Two characters cannot be written as a tracked insertion: a newline, which
    docx-editor turns into a tracked paragraph split this export does not
    write, and a tab, which docx-editor refuses outright (Word carries one as
    its own element, not as text). Everything else, whitespace included, goes
    in as written.

    Asked of the raw replacement rather than the rendered one: a newline or a
    tab survives rendering as itself, and the check has to hold whether or not
    the row was written before the rendered text existed.
    """
    if "\n" in text or "\r" in text:
        return FIRST_LINE_ONLY
    if "\t" in text:
        return NO_TABS
    return None
