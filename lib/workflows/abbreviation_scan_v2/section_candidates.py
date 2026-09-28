"""Cheap pre-check for whether a document could have an Abbreviations section.

The section agent locates the section by searching for "abbreviation",
"acronym" and "glossary". When none of them appears, the agent has nothing to
find, and on a long document it can spend its whole budget looking. This check
lets the node skip it. Plain text processing; no model is involved.

It matches the words anywhere rather than only on title-like lines: converted
PDFs glue titles onto running headers ("...Frontier ModelsAbbreviations") and
space out table-of-contents leaders, so a stricter test misses real sections.
"""

import re
from typing import List

_SECTION_WORD_RE = re.compile(r"abbreviation|acronym|glossary", re.IGNORECASE)


def find_candidate_lines(markdown: str) -> List[int]:
    """1-indexed lines containing "abbreviation", "acronym" or "glossary" (any case)."""
    return [
        number
        for number, line in enumerate(markdown.split("\n"), start=1)
        if _SECTION_WORD_RE.search(line)
    ]
