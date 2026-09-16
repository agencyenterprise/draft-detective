import type { ProposedEdit } from './proposed-edit';

/** The registry key the document's edit wash is filed under. */
export const EDIT_HIGHLIGHT_NAME = 'proposed-edit';

/**
 * The quote as the document renders it.
 *
 * `original_text` is taken verbatim from the markdown source, so it can carry
 * syntax the reader never sees: `**stress**` is rendered as `stress`, a link as
 * its label alone. Matching the raw quote against the rendered text would
 * therefore fail on exactly the passages an edit is most likely to touch, so
 * the syntax is stripped down to the characters that reach the page.
 */
export function stripMarkdown(text: string): string {
  return (
    text
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/`+/g, '')
      .replace(/~~/g, '')
      .replace(/\*{1,3}/g, '')
      // Only underscores standing outside a word: `snake_case` is a name in the
      // text, not emphasis, and stripping its underscores would stop it
      // matching. Written as two passes rather than one lookbehind for the sake
      // of older Safari.
      .replace(/(^|[^A-Za-z0-9])_{1,3}/g, '$1')
      .replace(/_{1,3}($|[^A-Za-z0-9])/g, '$1')
      .replace(/^[ \t]*(?:#{1,6}|>+)[ \t]*/gm, '')
      .replace(/^[ \t]*(?:[-+*]|\d+[.)])[ \t]+/gm, '')
  );
}

/** One space for any run of whitespace, since the rendered text wraps its own way. */
export function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/** What to look for in the rendered document, given an edit's raw quote. */
export function editSearchText(originalText: string): string {
  return normalizeWhitespace(stripMarkdown(originalText));
}

/**
 * Where `needle` sits in `haystack`, as `[start, end)`, or null.
 *
 * Falls back to a case-insensitive match: a quote can come back from a model
 * with a sentence's first letter recased, and highlighting the right span
 * matters more than insisting the letter matched.
 */
export function matchOffsets(haystack: string, needle: string): [number, number] | null {
  if (!needle) return null;
  let index = haystack.indexOf(needle);
  if (index === -1) index = haystack.toLowerCase().indexOf(needle.toLowerCase());
  if (index === -1) return null;
  return [index, index + needle.length];
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

/** A Range over the quote inside one block, or null if the block does not carry it. */
export function rangeInElement(block: Element, originalText: string): Range | null {
  const needle = editSearchText(originalText);
  if (!needle) return null;

  const index = buildTextIndex(block);
  const match = matchOffsets(index.text, needle);
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
 * The document's own blocks overlapping `[start, end]` source lines.
 *
 * Owner blocks only: a list and each of its items resolve to the same lines, so
 * searching both would find the quote twice and the outer block already carries
 * the items' text.
 */
export function blocksForLineRange(container: Element, start: number, end: number): HTMLElement[] {
  const blocks = container.querySelectorAll<HTMLElement>('[data-block-owner][data-line-start][data-line-end]');
  return Array.from(blocks).filter((block) => {
    const blockStart = Number(block.getAttribute('data-line-start'));
    const blockEnd = Number(block.getAttribute('data-line-end'));
    if (!Number.isFinite(blockStart) || !Number.isFinite(blockEnd)) return false;
    return blockStart <= end && blockEnd >= start;
  });
}

/**
 * A Range for each edit whose quote could be found, in the blocks its lines
 * cover. An edit never spans a blank line, so it lives inside a single block
 * and the first block that carries the quote is the right one.
 */
export function editRanges(container: Element, edits: ProposedEdit[]): Range[] {
  const ranges: Range[] = [];
  for (const edit of edits) {
    for (const block of blocksForLineRange(container, edit.start_line, edit.end_line)) {
      const range = rangeInElement(block, edit.original_text);
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

/** Paints `ranges` as the edit highlight, replacing whatever was there. */
export function setEditHighlight(ranges: Range[]): void {
  if (!supportsHighlightApi()) return;
  if (ranges.length === 0) {
    CSS.highlights.delete(EDIT_HIGHLIGHT_NAME);
    return;
  }
  CSS.highlights.set(EDIT_HIGHLIGHT_NAME, new Highlight(...ranges));
}

/** Takes the edit highlight off the document. */
export function clearEditHighlight(): void {
  if (!supportsHighlightApi()) return;
  CSS.highlights.delete(EDIT_HIGHLIGHT_NAME);
}
