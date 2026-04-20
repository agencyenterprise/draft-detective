"""Text sanitization utilities for control characters.

PDF-extracted markdown and LLM output can contain C0/C1 control characters
(null bytes, etc.) that break JSON serialization (OpenAI API), XML generation
(DOCX export), and PostgreSQL storage. This module provides a shared function
to strip these characters.
"""

import re

# Matches C0/C1 control characters except tab (\x09), newline (\x0a),
# and carriage return (\x0d) which are valid in text.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def strip_control_chars(text: str) -> str:
    """Remove C0/C1 control characters from text.

    Preserves tab, newline, and carriage return. Strips everything else
    in the U+0000–U+001F and U+007F–U+009F ranges.
    """
    return _CONTROL_CHAR_RE.sub("", text)
