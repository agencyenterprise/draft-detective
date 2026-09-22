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

/** One space for any run of whitespace, since the rendered text wraps its own way. */
export function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
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

/** Where one character of the flattened text came from. */
interface CharSource {
  node: Text;
  offset: number;
}

export interface TextIndex {
  /** The element's text with whitespace normalized, the way `display_text` is. */
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
 *
 * `displayText` is the edit's `display_text`: the quote as the document
 * renders it, worked out by the backend's CommonMark parser when the issue was
 * reported. Nothing is stripped here, so the page and the exported DOCX cannot
 * disagree about which characters an edit covers.
 */
export function rangeInElement(block: Element, displayText: string, occurrence?: number): Range | null {
  const needle = normalizeWhitespace(displayText);
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
 * quote is the right one.
 *
 * Which occurrence to mark comes off the edit itself: `display_occurrence`
 * counted the repeats on the edit's own source line when the issue was
 * reported, so it only applies to a block that is exactly that line. A block
 * covering several source lines -- a paragraph written across two lines, a
 * list -- is a different haystack, and the count would not be its own; there
 * the quote is marked only when the block carries it once, and left unmarked
 * rather than marked in the wrong place.
 */
export function editRanges(container: Element, edits: ProposedEdit[]): Range[] {
  const ranges: Range[] = [];
  for (const edit of edits) {
    for (const block of blocksForLineRange(container, edit.start_line, edit.end_line)) {
      const blockStart = Number(block.getAttribute('data-line-start'));
      const blockEnd = Number(block.getAttribute('data-line-end'));
      const isOwnLine = blockStart === edit.start_line && blockEnd === edit.start_line;
      const range = rangeInElement(block, edit.display_text, isOwnLine ? edit.display_occurrence : undefined);
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
