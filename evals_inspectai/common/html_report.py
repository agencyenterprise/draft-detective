"""Parsing helpers for scoring the self-contained HTML reports.

The `review-assistant` workflows deliver a single self-contained HTML document
rather than structured issues, so their scorers work on the rendered text. The
skill's rules are mostly about *where* text sits — reviewer wording inside a
marked quote, the assessor's own wording outside it — so these helpers keep the
two apart.

Uses the stdlib HTML parser rather than BeautifulSoup: bs4 is only present
transitively, and the parsing needed here is shallow.
"""

import re
from html.parser import HTMLParser

# Elements whose text is markup machinery, not readable content.
_NON_TEXT_TAGS = frozenset({"script", "style", "head", "title"})

# Elements that mark reviewer text reproduced verbatim. `q` is included for
# completeness; the skill asks for blockquotes.
_QUOTE_TAGS = frozenset({"blockquote", "q"})

# Tags that imply a line break when flattening markup to text, so that adjacent
# blocks do not run together into words that were never adjacent.
_BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "tr",
        "td",
        "th",
        "table",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
        "header",
        "footer",
        "blockquote",
        "hr",
        "pre",
    }
)

_WHITESPACE = re.compile(r"\s+")


_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


class _TextExtractor(HTMLParser):
    """Flattens an HTML document into text, tracking quote nesting.

    Also records where each heading begins, so a section can be located by its
    heading rather than by any mention of its name in the prose.
    """

    def __init__(
        self,
        break_classes: frozenset[str] = frozenset(),
        break_ids: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(convert_charrefs=True)
        self._break_classes = break_classes
        self._break_ids = break_ids
        # Offsets into the flattened text where a page break starts.
        self.break_offsets: list[int] = []
        self._all: list[str] = []
        self._quoted: list[str] = []
        self._unquoted: list[str] = []
        self._skip_depth = 0
        self._quote_depth = 0
        self._length = 0
        self._heading_start: int | None = None
        self._heading_buffer: list[str] = []
        # (offset into the flattened text, heading text) in document order.
        self.headings: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if self._breaks_page(dict(attrs)):
            self.break_offsets.append(self._length)
        if tag in _NON_TEXT_TAGS:
            self._skip_depth += 1
        if tag in _QUOTE_TAGS:
            self._quote_depth += 1
        if tag in _HEADING_TAGS:
            self._heading_start = self._length
            self._heading_buffer = []
        if tag in _BLOCK_TAGS:
            self._emit("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _NON_TEXT_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in _QUOTE_TAGS and self._quote_depth:
            self._quote_depth -= 1
        if tag in _HEADING_TAGS and self._heading_start is not None:
            self.headings.append((self._heading_start, "".join(self._heading_buffer)))
            self._heading_start = None
        if tag in _BLOCK_TAGS:
            self._emit("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._heading_start is not None:
            self._heading_buffer.append(data)
        self._emit(data)

    def _breaks_page(self, attrs: dict) -> bool:
        """Whether this element starts a new printed page."""
        if _PAGE_BREAK.search(attrs.get("style") or ""):
            return True
        if (attrs.get("id") or "") in self._break_ids:
            return True
        return bool(set((attrs.get("class") or "").split()) & self._break_classes)

    def _emit(self, text: str) -> None:
        self._all.append(text)
        self._length += len(text)
        if self._quote_depth:
            self._quoted.append(text)
        else:
            self._unquoted.append(text)

    @property
    def text(self) -> str:
        return "".join(self._all)

    @property
    def quoted_text(self) -> str:
        return "".join(self._quoted)

    @property
    def unquoted_text(self) -> str:
        return "".join(self._unquoted)


class HtmlReport:
    """A parsed HTML report, with its text split by quote membership.

    Attributes:
        html: The raw HTML source.
        text: All readable text, normalised for comparison.
        quoted_text: Text inside `<blockquote>`/`<q>` — the reviewer's words.
        unquoted_text: Everything else — the workflow's own contribution.
        raw_text / raw_unquoted_text: The same text with whitespace collapsed
            but no character folding, for checks about the characters
            themselves (see `voice_tells`).
        headings: (offset, normalised text) for every heading, in document
            order, used to locate a section by its heading.
    """

    def __init__(self, html: str) -> None:
        break_classes, break_ids = page_break_selectors(html)
        parser = _TextExtractor(frozenset(break_classes), frozenset(break_ids))
        parser.feed(html)
        parser.close()

        self.html = html
        # The uncollapsed concatenation. `break_offsets` and heading offsets
        # index into this, so it is the only string the part split can be cut
        # from -- `text` and `raw_text` have had their whitespace collapsed and
        # no longer line up with the offsets the parser recorded.
        self._raw = parser.text
        self.text = normalize(parser.text)
        self.quoted_text = normalize(parser.quoted_text)
        self.unquoted_text = normalize(parser.unquoted_text)
        self.raw_text = _WHITESPACE.sub(" ", parser.text).strip()
        self.raw_unquoted_text = _WHITESPACE.sub(" ", parser.unquoted_text).strip()
        self._text_length = parser._length
        self.headings = [(offset, normalize(text)) for offset, text in parser.headings]
        self.break_offsets = parser.break_offsets

    @property
    def part2(self) -> str:
        """Normalised text from the first page break onward.

        The reports put Part 1 -- the summary a QAM reads first -- above a
        forced page break and the point-by-point detail below it, so the break
        is the part boundary. Slicing there is what lets a check ask about
        Part 2 alone rather than about the document as a whole, which matters
        whenever Part 1 recaps in prose something Part 2 is supposed to do: a
        summary saying "two points were partially addressed" otherwise stands
        in for a Part 2 that never uses the scale at all.

        Falls back to the whole document when nothing forces a break. There is
        no second part to isolate in that case, and `two_part_layout` already
        fails the report for it, so there is no need to fail twice.
        """
        return (
            normalize(self._raw[min(self.break_offsets) :])
            if self.break_offsets
            else self.text
        )

    @property
    def part1(self) -> str:
        """Normalised text before the first page break: the summary a QAM reads.

        The whole document when nothing forces a break, for the same reason as
        `part2`.
        """
        return (
            normalize(self._raw[: min(self.break_offsets)])
            if self.break_offsets
            else self.text
        )

    @property
    def part2_raw(self) -> str:
        """`part2`, whitespace-collapsed but not character-folded.

        For checks about the characters themselves -- point ids are matched
        case-sensitively, and `normalize` lowercases.
        """
        if not self.break_offsets:
            return self.raw_text
        return _WHITESPACE.sub(" ", self._raw[min(self.break_offsets) :]).strip()

    def contains(self, snippet: str) -> bool:
        """Whether the report's text contains `snippet`, ignoring whitespace."""
        return normalize(snippet) in self.text

    def quotes(self, snippet: str) -> bool:
        """Whether `snippet` appears inside a marked quote."""
        return normalize(snippet) in self.quoted_text

    def heading_offset(self, pattern: re.Pattern[str]) -> float | None:
        """Where the first heading matching `pattern` sits, as a document fraction."""
        if not self._text_length:
            return None
        for offset, text in self.headings:
            if pattern.match(text):
                return offset / self._text_length
        return None

    @property
    def part_boundary(self) -> float | None:
        """Where the document breaks into its second part, as a fraction.

        Returns None when nothing in the document forces a page break, which
        means there is no visible split at all.
        """
        if not self._text_length or not self.break_offsets:
            return None
        return min(self.break_offsets) / self._text_length


def normalize(text: str) -> str:
    """Collapse whitespace and normalise quote/dash characters for comparison.

    Reproducing a memo "verbatim" through Markdown conversion, an LLM, and HTML
    escaping will not preserve line wrapping or the exact flavour of a quote
    character, and holding the output to that would only measure typography.
    Word sequence is what the skill's rule is actually about, so that is what
    survives normalisation.
    """
    text = (
        text.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", " ")
    )
    return _WHITESPACE.sub(" ", text).strip().lower()


# --- Self-containment -------------------------------------------------------

# Attributes whose value the renderer fetches. A self-contained document may
# only point them at a data: URI, so anything else -- an absolute URL, a
# site-relative path like "/logo.png", or a sibling file -- is a violation.
# `srcset` is listed before `src` so the alternation does not match its prefix,
# and the leading \b keeps `data` from matching `metadata=` or `data-*=`.
_FETCHED_ATTR = re.compile(
    r"""\b(srcset|src|poster|background|data)\s*="""
    r"""(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)

# Attributes that reach the network without being a fetched resource. `href` is
# checked only for network targets: on a <link> it pulls a stylesheet, but on an
# <a> it is a hyperlink the reader may click, which does not stop the document
# from standing alone.
_EXTERNAL_LINK = re.compile(
    r"""\b(?:href|action)\s*=\s*["']?\s*(?:https?:)?//""",
    re.IGNORECASE,
)

# CSS resource references: `@font-face { src: url(...) }`, `background: url(...)`
# and friends. These use a colon rather than an `=`, so the attribute patterns
# above never see them, which is how a webfont used to slip through.
_CSS_URL = re.compile(r"""url\(\s*["']?\s*([^)"']*)""", re.IGNORECASE)

_SCRIPT_TAG = re.compile(r"<\s*script\b", re.IGNORECASE)
_STYLESHEET_LINK = re.compile(
    r"<\s*link\b[^>]*rel\s*=\s*[\"']?stylesheet", re.IGNORECASE
)
_IMPORT_RULE = re.compile(r"@import\b", re.IGNORECASE)


def _resource_targets(attr: str, value: str) -> list[str]:
    """Every URL an attribute value offers, not just the first.

    Only `srcset` carries more than one. It is a comma-separated list of
    "url descriptor" pairs, so reading up to the first space inspects only the
    leading candidate: a list whose first entry is a data URI and whose second
    is a CDN would pass while still fetching from the CDN.

    Candidates are split on a comma *followed by whitespace* rather than on any
    comma, because a data URI carries commas of its own -- the one after
    `;base64` is part of the URL. Those are never followed by a space, since
    base64 has none, so the distinction holds for the images these reports
    embed.
    """
    if attr.lower() != "srcset":
        return [value.strip()]
    return [c.split()[0] for c in re.split(r",\s+", value) if c.split()]


def _stays_in_document(value: str) -> bool:
    """Whether a resource reference resolves without leaving the document."""
    target = value.strip().strip("\"'").lower()
    return not target or target.startswith(("data:", "#", "about:blank"))


def self_containment_violations(html: str) -> list[str]:
    """Return the ways `html` fails the workflows' self-contained requirement.

    All three review-assistant system prompts require a single self-contained
    document: no external stylesheets, fonts, scripts or images, and no
    `<script>` of any kind. An empty list means the document complies.

    "External" is judged by whether the reference resolves inside the document,
    not by whether it names a host. A report saved to disk and mailed to a QAM
    renders a site-relative `<img src="/chart.png">` as a broken image just as
    surely as it does an absolute URL, so both count.
    """
    violations: list[str] = []
    if _SCRIPT_TAG.search(html):
        violations.append("contains a <script> tag")
    if _STYLESHEET_LINK.search(html):
        violations.append("links an external stylesheet")
    if _IMPORT_RULE.search(html):
        violations.append("uses an @import rule")

    fetched = [
        f"{attr}={candidate[:40]}"
        for attr, *values in _FETCHED_ATTR.findall(html)
        for candidate in _resource_targets(attr, "".join(values))
        if not _stays_in_document(candidate)
    ]
    if fetched:
        violations.append(
            f"fetches {len(fetched)} resource(s) from outside the document: "
            + ", ".join(sorted(set(fetched))[:3])
        )

    links = _EXTERNAL_LINK.findall(html)
    if links:
        violations.append(f"references {len(links)} external URL(s)")

    css = [url for url in _CSS_URL.findall(html) if not _stays_in_document(url)]
    if css:
        violations.append(
            f"{len(css)} CSS url() reference(s) leave the document: "
            + ", ".join(sorted(set(u[:40] for u in css))[:3])
        )
    return violations


# --- Reviewer point IDs -----------------------------------------------------

# A1, B12, A1.2 — a reviewer letter, a point number, and an optional sub-point.
# The leading lookbehind keeps it out of words and longer identifiers (the "A1"
# in "DNA123"). The trailing lookaheads reject a longer number and a decimal
# tail, but deliberately allow a bare period after the id: reports label points
# "A1." as often as "A1", and rejecting that undercounted every point in a
# section and made the numbering look full of gaps.
_POINT_ID = re.compile(
    r"(?<![A-Za-z0-9])([A-Z])(\d{1,2})(?:\.(\d{1,2}))?(?!\d)(?!\.\d)"
)


class PointId(str):
    """A reviewer point ID such as `A1` or `A1.2`."""

    @property
    def reviewer(self) -> str:
        return self[0]

    @property
    def number(self) -> int:
        return int(self[1:].split(".")[0])

    @property
    def is_subpoint(self) -> bool:
        return "." in self


def find_point_ids(text: str) -> list[PointId]:
    """Return every reviewer point ID in `text`, in order of appearance."""
    ids: list[PointId] = []
    for letter, number, sub in _POINT_ID.findall(text):
        ids.append(
            PointId(
                f"{letter}{int(number)}.{int(sub)}" if sub else f"{letter}{int(number)}"
            )
        )
    return ids


def top_level_ids_by_reviewer(ids: list[PointId]) -> dict[str, set[int]]:
    """Group point numbers by reviewer letter, ignoring sub-point suffixes."""
    grouped: dict[str, set[int]] = {}
    for point_id in ids:
        grouped.setdefault(point_id.reviewer, set()).add(point_id.number)
    return grouped


# --- Voice tells ------------------------------------------------------------

# `voice-and-tone` bans these from the workflow's own prose. They are only
# checked outside quotes, since a reviewer may well have written any of them
# and the memo is reproduced verbatim.
_EMOJI = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]")


def voice_tells(raw_unquoted_text: str) -> dict[str, int]:
    """Count generic-AI voice tells in the workflow's own (unquoted) prose.

    Takes `HtmlReport.raw_unquoted_text`, not the normalised text: normalisation
    folds em dashes to hyphens, which is exactly the distinction being counted.
    """
    return {
        "em_dash": raw_unquoted_text.count("—"),
        "exclamation": raw_unquoted_text.count("!"),
        "emoji": len(_EMOJI.findall(raw_unquoted_text)),
    }


# --- Two-part layout -------------------------------------------------------

# How much of the document the first part may occupy. Part 2 reproduces every
# memo in full, so a compliant one-page first part lands near 0.2 (observed
# 0.12-0.25 across 20 real runs); a first part that retells the memos roughly
# doubles that. The threshold sits between.
_MAX_FIRST_PART_SHARE = 0.33

_PAGE_BREAK = re.compile(
    r"(?:break-before|page-break-before)\s*:\s*(?:page|always)", re.I
)

# One CSS rule: the selector list, then the declaration block.
_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
# The class and id tokens inside a selector.
_SELECTOR_TOKEN = re.compile(r"[.#]([A-Za-z_][\w-]*)")


def page_break_selectors(html: str) -> tuple[set[str], set[str]]:
    """Return the (classes, ids) whose CSS rules force a page break.

    The two-part layout is identified by where the document breaks for print,
    not by what the headings are called: the skill asks for the split to be
    visible, and leaves the wording to the writer. Reports express the break
    either as a class (`.part2{break-before:page}`) or inline on the element.
    """
    classes: set[str] = set()
    ids: set[str] = set()
    for selector, declarations in _CSS_RULE.findall(html):
        if not _PAGE_BREAK.search(declarations):
            continue
        for match in _SELECTOR_TOKEN.finditer(selector):
            token = match.group(0)
            (classes if token[0] == "." else ids).add(match.group(1))
    return classes, ids


def two_part_layout(report: "HtmlReport") -> tuple[bool, str]:
    """Whether the report splits into a short first part and a second part.

    The skill requires the split to be visible and Part 2 demoted to a new
    printed page, but leaves the headings to the writer: reports label the
    parts "Part 1"/"Part 2", or descriptively ("Revision-planning summary",
    then "Reviewer memos reproduced verbatim"). Both satisfy it, so the check
    keys on the page break that separates them rather than on any wording.

    What it still holds the report to is the shape the skill's "lead with the
    decision" section is about: a real first part exists, and it is short
    relative to the reference material that follows.
    """
    boundary = report.part_boundary
    if boundary is None:
        return False, "no page break separating the two parts"
    if boundary == 0:
        return False, "the page break is at the top; no first part before it"
    if boundary > _MAX_FIRST_PART_SHARE:
        return (
            False,
            f"first part runs to {boundary:.0%} of the document, over the "
            f"{_MAX_FIRST_PART_SHARE:.0%} budget",
        )
    return True, f"first part is {boundary:.0%} of the document"


# --- Tables ----------------------------------------------------------------


class _TableExtractor(HTMLParser):
    """Collects every table as rows of cell text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif self._cell is not None:
            # A separator between the cell's child elements. Without it a cell
            # built as "<strong>9</strong><br>A1, A2" flattens to "9A1, A2",
            # and an id glued to a preceding digit is not an id any scanner
            # will recognise.
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag not in ("td", "th", "tr", "table") and self._cell is not None:
            self._cell.append(" ")
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_WHITESPACE.sub(" ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def tables(html: str) -> list[list[list[str]]]:
    """Every table in the document, as rows of cell text."""
    parser = _TableExtractor()
    parser.feed(html)
    parser.close()
    return parser.tables


# --- Point-ID ranges -------------------------------------------------------

# "A1-A8" or "A1–8": reports abbreviate a run of consecutive points rather than
# listing each one, which a plain id scan reads as two ids with a hole between.
_ID_RANGE = re.compile(
    r"(?<![A-Za-z0-9])([A-Z])(\d{1,2})\s*[-–—]\s*([A-Z]?)(\d{1,2})(?!\d)"
)


def expand_point_ids(text: str) -> list[PointId]:
    """Point IDs in `text`, expanding an abbreviated range into its members.

    `A1-A8` means eight points, not two. Ranges are expanded and their spans
    removed before the remaining text is scanned, so nothing is counted twice.
    A range whose ends disagree on the reviewer letter (`A3-B2`) is left to the
    plain scan, since it is not a run of one reviewer's points.
    """
    ids: list[PointId] = []
    spans: list[tuple[int, int]] = []
    for match in _ID_RANGE.finditer(text):
        letter, start, end_letter, end = match.groups()
        if end_letter and end_letter != letter:
            continue
        first, last = int(start), int(end)
        if not first <= last:
            continue
        ids.extend(PointId(f"{letter}{n}") for n in range(first, last + 1))
        spans.append(match.span())

    remainder = text
    for start_at, end_at in reversed(spans):
        remainder = remainder[:start_at] + " " + remainder[end_at:]
    ids.extend(find_point_ids(remainder))
    return ids
