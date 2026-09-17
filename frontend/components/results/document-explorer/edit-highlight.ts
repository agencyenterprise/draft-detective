import type { ProposedEdit } from './proposed-edit';

/** The registry key the document's edit wash is filed under. */
export const EDIT_HIGHLIGHT_NAME = 'proposed-edit';

/** The id of the style element that paints the edit highlight. */
export const EDIT_HIGHLIGHT_STYLE_ID = 'proposed-edit-highlight-style';

/**
 * How the highlighted span looks.
 *
 * Amber rather than a severity colour, and wavy-underlined: the block already
 * carries its severity wash, so the span has to say something different --
 * "these characters are what changes" -- without competing with it.
 *
 * Injected at runtime rather than written in globals.css: the production CSS
 * pipeline (Turbopack's parser) rejects the `::highlight()` pseudo-element,
 * and the rule is only meaningful in browsers that have the Highlight API in
 * the first place.
 */
const EDIT_HIGHLIGHT_CSS = `
::highlight(${EDIT_HIGHLIGHT_NAME}) {
  background-color: rgb(245 158 11 / 0.35);
  text-decoration: underline wavy rgb(180 83 9 / 0.7);
  text-underline-offset: 3px;
}
.dark ::highlight(${EDIT_HIGHLIGHT_NAME}) {
  background-color: rgb(245 158 11 / 0.28);
  text-decoration: underline wavy rgb(252 211 77 / 0.75);
}
`;

/**
 * The quote as the document renders it.
 *
 * `original_text` is taken verbatim from the markdown source, so it can carry
 * syntax the reader never sees: `**stress**` is rendered as `stress`, a link as
 * its label alone. Matching the raw quote against the rendered text would
 * therefore fail on exactly the passages an edit is most likely to touch, so
 * the syntax is stripped down to the characters that reach the page.
 *
 * A heading hash, a blockquote arrow and a list marker are only syntax where a
 * line begins. `2019. Annual report` quoted from the middle of a reference
 * entry keeps its year; `1. First item` quoted from the top of a list item
 * loses the marker. A caller that knows the quote did not start its source
 * line passes `atLineStart` as false.
 */
export function stripMarkdown(text: string, atLineStart = true): string {
  // The pass order mirrors the Python port: images, links, code fences and
  // strikethrough, then emphasis, then underscores.
  const stripped = stripEmphasis(
    protectEscaped(text).replace(IMAGE, '$1').replace(LINK, '$1').replace(/`+/g, '').replace(/~~/g, ''),
  )
    // Only underscores standing outside a word: `snake_case` is a name in the
    // text, not emphasis, and stripping its underscores would stop it
    // matching. Written as two passes rather than one lookbehind for the sake
    // of older Safari.
    .replace(/(^|[^A-Za-z0-9])_{1,3}/g, '$1')
    .replace(/_{1,3}($|[^A-Za-z0-9])/g, '$1');
  return restoreEscaped(
    atLineStart
      ? stripped.replace(/^[ \t]*(?:#{1,6}|>+)[ \t]*/gm, '').replace(/^[ \t]*(?:[-+*]|\d+[.)])[ \t]+/gm, '')
      : stripped,
  );
}

/**
 * A link label may itself hold one level of brackets: MarkItDown writes a DOCX
 * footnote reference as `[[1]](#footnote-2)`, which the page shows as `[1]`.
 */
/**
 * Emphasis, only where a delimiter is actually paired: an opening run of stars
 * has to be followed by a non-space character and its closing run preceded by
 * one, the way CommonMark decides what emphasizes. Longest run first, so
 * `***both***` is not read as bold plus a stray star.
 *
 * A star with no partner is text the page shows: `2 * 3` is a product and
 * `5*3` keeps its star, because a single star between two non-space characters
 * with nothing to close it is not emphasis. The Python port of these rules, in
 * `lib/services/docx/edit_text.py`, has to agree character for character.
 */
const EMPHASIS = [
  /\*{3}([^\s](?:[\s\S]*?[^\s])?)\*{3}/g,
  /\*{2}([^\s](?:[\s\S]*?[^\s])?)\*{2}/g,
  /\*([^\s](?:[\s\S]*?[^\s])?)\*/g,
];

function stripEmphasis(text: string): string {
  return EMPHASIS.reduce((stripped, pattern) => stripped.replace(pattern, '$1'), text);
}

const LINK = /\[((?:[^[\]]|\[[^[\]]*\])*)\]\([^)]*\)/g;
const IMAGE = /!\[((?:[^[\]]|\[[^[\]]*\])*)\]\([^)]*\)/g;

/**
 * Backslash-escaped punctuation, as CommonMark defines it: the renderer shows
 * the character itself, so `foo\_bar` in the source reads `foo_bar` on the
 * page. MarkItDown writes these escapes for any literal punctuation in DOCX
 * prose that would otherwise be read as syntax.
 */
const ESCAPED_PUNCTUATION = /\\([!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~])/g;

/** Private-use code points stand in for escaped characters while syntax is stripped. */
const PLACEHOLDER_BASE = 0xe000;
const PLACEHOLDER_RANGE = /[\uE000-\uE0FF]/g;

/**
 * An escaped character must survive the stripping passes as the literal it
 * stands for, not be read as syntax: `\*` is an asterisk on the page, not an
 * emphasis marker. Each one is swapped for a private-use placeholder first and
 * put back as the bare character at the end.
 */
function protectEscaped(text: string): string {
  return text.replace(ESCAPED_PUNCTUATION, (_, char: string) =>
    String.fromCharCode(PLACEHOLDER_BASE + char.charCodeAt(0)),
  );
}

function restoreEscaped(text: string): string {
  return text.replace(PLACEHOLDER_RANGE, (placeholder) =>
    String.fromCharCode(placeholder.charCodeAt(0) - PLACEHOLDER_BASE),
  );
}

/** One space for any run of whitespace, since the rendered text wraps its own way. */
export function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/** What to look for in the rendered document, given an edit's raw quote. */
export function editSearchText(originalText: string, atLineStart = true): string {
  return normalizeWhitespace(stripMarkdown(originalText, atLineStart));
}

/** Start offset of every occurrence of `needle` in `haystack`, overlapping ones included. */
export function allOffsets(haystack: string, needle: string): number[] {
  const offsets: number[] = [];
  if (!needle) return offsets;
  for (let index = haystack.indexOf(needle); index !== -1; index = haystack.indexOf(needle, index + 1)) {
    offsets.push(index);
  }
  return offsets;
}

/**
 * Where the `occurrence`-th (0-based) `needle` sits in `haystack`, as
 * `[start, end)`, or null.
 *
 * Falls back to a case-insensitive match: a quote can come back from a model
 * with a sentence's first letter recased, and highlighting the right span
 * matters more than insisting the letter matched.
 */
export function matchOffsets(haystack: string, needle: string, occurrence = 0): [number, number] | null {
  if (!needle) return null;
  let offsets = allOffsets(haystack, needle);
  if (offsets.length === 0) offsets = allOffsets(haystack.toLowerCase(), needle.toLowerCase());
  const index = offsets[occurrence];
  if (index === undefined) return null;
  return [index, index + needle.length];
}

/** Marks where the quote starts in the source while the syntax around it is stripped. */
const QUOTE_MARK = '\uE1FF';

/**
 * Which occurrence of the rendered quote an edit means, worked out from the
 * markdown source, or null when the source does not settle it.
 *
 * The backend guarantees `original_text` is unique on its own line as written,
 * but stripping the syntax can create duplicates: `**Figure 3**` is a unique
 * quote in `Figure 3 and **Figure 3**` and the page shows `Figure 3` twice. The
 * block's source lines are stripped the same way the quote is, with a marker
 * at the quote's position, so counting the stripped quote before the marker
 * says which rendered occurrence is the one the edit was anchored to.
 *
 * `atLineStart` applies to the quote alone: the block's lines are stripped as
 * the lines they are, markers and all.
 */
export function sourceOccurrence(
  sourceLines: readonly string[],
  blockStart: number,
  blockEnd: number,
  edit: Pick<ProposedEdit, 'original_text' | 'start_line'>,
  atLineStart = true,
): number | null {
  const line = sourceLines[edit.start_line - 1];
  if (line === undefined) return null;
  const normalizedLine = normalizeWhitespace(line);
  const quoteAt = allOffsets(normalizedLine, normalizeWhitespace(edit.original_text));
  if (quoteAt.length !== 1) return null;

  const marked = normalizedLine.slice(0, quoteAt[0]) + QUOTE_MARK + normalizedLine.slice(quoteAt[0]);
  const first = Math.max(1, blockStart);
  const last = Math.min(sourceLines.length, blockEnd);
  const stripped: string[] = [];
  for (let number = first; number <= last; number++) {
    const text = number === edit.start_line ? marked : normalizeWhitespace(sourceLines[number - 1]);
    stripped.push(normalizeWhitespace(stripMarkdown(text)));
  }
  const haystack = stripped.join(' ');
  const markAt = haystack.indexOf(QUOTE_MARK);
  if (markAt === -1) return null;
  // The marker sits where the stripped quote starts, so the occurrences that
  // begin before it are exactly the ones the page shows ahead of the edit's.
  const clean = haystack.replace(QUOTE_MARK, '');
  return allOffsets(clean, editSearchText(edit.original_text, atLineStart)).filter((offset) => offset < markAt).length;
}

/**
 * Whether the quote opens its own markdown line, which decides how it is
 * stripped: `2019.` is a list marker at the head of a line and a year anywhere
 * else in it. Unknown lines are treated as if the quote started them, which is
 * what a caller without the source gets.
 */
function startsItsSourceLine(
  sourceLines: readonly string[],
  edit: Pick<ProposedEdit, 'original_text' | 'start_line'>,
): boolean {
  const line = sourceLines[edit.start_line - 1];
  if (line === undefined) return true;
  return normalizeWhitespace(line).startsWith(normalizeWhitespace(edit.original_text));
}

/** Where one character of the flattened text came from. */
interface CharSource {
  node: Text;
  offset: number;
}

export interface TextIndex {
  /** The element's text with whitespace normalized, as {@link editSearchText} leaves a quote. */
  text: string;
  /** `sources[i]` is the node and offset `text[i]` was read from. */
  sources: CharSource[];
}

/**
 * An element's text nodes flattened into one string, with every character
 * still pointing back at the node it came from.
 *
 * The mapping is what makes a character-level highlight possible without
 * touching the DOM: a match in the flattened string becomes a Range over the
 * original nodes, so the rendered markup — the `strong`, the link, the
 * footnote — is left exactly as it was.
 */
export function buildTextIndex(root: Element): TextIndex {
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const sources: CharSource[] = [];
  let text = '';
  // Whitespace is emitted lazily so a run of it collapses to one space and a
  // leading run to nothing, matching what the quote was normalized to.
  let pendingSpace = false;

  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const value = node.nodeValue ?? '';
    for (let offset = 0; offset < value.length; offset++) {
      const char = value[offset];
      if (/\s/.test(char)) {
        pendingSpace = text.length > 0;
        continue;
      }
      const source = { node: node as Text, offset };
      if (pendingSpace) {
        text += ' ';
        sources.push(source);
        pendingSpace = false;
      }
      text += char;
      sources.push(source);
    }
  }

  return { text, sources };
}

/**
 * A Range over the `occurrence`-th quote inside one block, or null if the block
 * does not carry it. Without an occurrence, the quote must appear exactly once
 * in the block: guessing between repeats would mark the wrong words.
 */
export function rangeInElement(
  block: Element,
  originalText: string,
  occurrence?: number,
  atLineStart = true,
): Range | null {
  const needle = editSearchText(originalText, atLineStart);
  if (!needle) return null;

  const index = buildTextIndex(block);
  if (occurrence === undefined && allOffsets(index.text, needle).length > 1) return null;
  const match = matchOffsets(index.text, needle, occurrence ?? 0);
  if (!match) return null;

  const start = index.sources[match[0]];
  const end = index.sources[match[1] - 1];
  if (!start || !end) return null;

  const range = block.ownerDocument.createRange();
  range.setStart(start.node, start.offset);
  range.setEnd(end.node, end.offset + 1);
  return range;
}

/**
 * Every block overlapping `[start, end]` source lines, tightest first.
 *
 * Nested blocks are included on purpose: a list or table is one owner block
 * spanning all of its lines, and its items each carry their own line range.
 * The backend only guarantees a quote is unique within the edit's own lines,
 * so a search over the whole list could land on an identical phrase in an
 * earlier item. Trying the narrowest block first keeps the match on the line
 * the edit was anchored to; the owner block is still there as a fallback for
 * text that sits directly in it.
 */
export function blocksForLineRange(container: Element, start: number, end: number): HTMLElement[] {
  const blocks = container.querySelectorAll<HTMLElement>('[data-line-start][data-line-end]');
  const overlapping: { block: HTMLElement; span: number }[] = [];
  blocks.forEach((block) => {
    const blockStart = Number(block.getAttribute('data-line-start'));
    const blockEnd = Number(block.getAttribute('data-line-end'));
    if (!Number.isFinite(blockStart) || !Number.isFinite(blockEnd)) return;
    if (blockStart <= end && blockEnd >= start) overlapping.push({ block, span: blockEnd - blockStart });
  });
  // A stable sort, so blocks with the same span keep document order.
  return overlapping.sort((a, b) => a.span - b.span).map((entry) => entry.block);
}

/**
 * A Range for each edit whose quote could be found, in the blocks its lines
 * cover. An edit sits on one source line, so the narrowest block carrying the
 * quote is the right one. With the markdown source at hand, a quote the page
 * shows more than once inside that block is resolved to the occurrence the
 * edit was anchored to; without it, such a quote is left unmarked rather than
 * marked in the wrong place. The source also says whether the quote opened its
 * line, which is what keeps a mid-line `2019.` from being read as a list
 * marker.
 */
export function editRanges(container: Element, edits: ProposedEdit[], sourceLines?: readonly string[]): Range[] {
  const ranges: Range[] = [];
  for (const edit of edits) {
    const atLineStart = sourceLines ? startsItsSourceLine(sourceLines, edit) : true;
    for (const block of blocksForLineRange(container, edit.start_line, edit.end_line)) {
      const occurrence = sourceLines
        ? sourceOccurrence(
            sourceLines,
            Number(block.getAttribute('data-line-start')),
            Number(block.getAttribute('data-line-end')),
            edit,
            atLineStart,
          )
        : null;
      const range = rangeInElement(block, edit.original_text, occurrence ?? undefined, atLineStart);
      if (range) {
        ranges.push(range);
        break;
      }
    }
  }
  return ranges;
}

/**
 * Whether the browser can paint a highlight without the DOM being rewritten.
 * Where it cannot — Firefox before 140, older Safari — the edits are still read
 * in the note; only the mark on the passage is missing.
 */
export function supportsHighlightApi(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof CSS !== 'undefined' &&
    'highlights' in CSS &&
    typeof window.Highlight === 'function'
  );
}

/** Adds the highlight's style rule to the page once, when it is first needed. */
export function ensureEditHighlightStyle(doc: Document = document): void {
  if (doc.getElementById(EDIT_HIGHLIGHT_STYLE_ID)) return;
  const style = doc.createElement('style');
  style.id = EDIT_HIGHLIGHT_STYLE_ID;
  style.textContent = EDIT_HIGHLIGHT_CSS;
  doc.head.appendChild(style);
}

/** Paints `ranges` as the edit highlight, replacing whatever was there. */
export function setEditHighlight(ranges: Range[]): void {
  if (!supportsHighlightApi()) return;
  if (ranges.length === 0) {
    CSS.highlights.delete(EDIT_HIGHLIGHT_NAME);
    return;
  }
  ensureEditHighlightStyle();
  CSS.highlights.set(EDIT_HIGHLIGHT_NAME, new Highlight(...ranges));
}

/** Takes the edit highlight off the document. */
export function clearEditHighlight(): void {
  if (!supportsHighlightApi()) return;
  CSS.highlights.delete(EDIT_HIGHLIGHT_NAME);
}
