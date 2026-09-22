import { IssueEditStatus } from '@/lib/generated-api';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  EDIT_HIGHLIGHT_NAME,
  blocksForLineRange,
  buildTextIndex,
  clearEditHighlight,
  ensureEditHighlightStyle,
  EDIT_HIGHLIGHT_STYLE_ID,
  allOffsets,
  editRanges,
  matchOffsets,
  normalizeWhitespace,
  rangeInElement,
  setEditHighlight,
  supportsHighlightApi,
} from './edit-highlight';
import type { ProposedEdit } from './proposed-edit';

function edit(overrides: Partial<ProposedEdit> = {}): ProposedEdit {
  return {
    id: 'edit-1',
    issue_id: 'issue-1',
    original_text: 'the text',
    replacement_text: 'the better text',
    display_text: 'the text',
    display_occurrence: 0,
    display_replacement: 'the better text',
    start_line: 1,
    end_line: 1,
    rationale: 'because',
    status: IssueEditStatus.Proposed,
    ...overrides,
  };
}

/** A detached element carrying `html`, so the tree walker has real text nodes. */
function element(html: string): HTMLElement {
  const host = document.createElement('div');
  host.innerHTML = html;
  return host;
}

describe('normalizeWhitespace', () => {
  it('collapses whitespace runs and trims the edges', () => {
    expect(normalizeWhitespace('  a \n\t b   c  ')).toBe('a b c');
  });
});

describe('matchOffsets', () => {
  it('finds an exact hit', () => {
    expect(matchOffsets('the quick fox', 'quick')).toEqual([4, 9]);
  });

  it('falls back to a case-insensitive match', () => {
    expect(matchOffsets('The quick fox', 'the quick')).toEqual([0, 9]);
  });

  it('returns null when the needle is absent', () => {
    expect(matchOffsets('the quick fox', 'slow')).toBeNull();
  });

  it('returns null for an empty needle', () => {
    expect(matchOffsets('the quick fox', '')).toBeNull();
  });
});

describe('allOffsets', () => {
  it('lists every start offset, overlapping ones included', () => {
    expect(allOffsets('Figure 3 and Figure 3', 'Figure 3')).toEqual([0, 13]);
    expect(allOffsets('aaa', 'aa')).toEqual([0, 1]);
    expect(allOffsets('abc', '')).toEqual([]);
  });
});

describe('matchOffsets with an occurrence', () => {
  it('picks the requested occurrence and returns null past the last one', () => {
    expect(matchOffsets('Figure 3 and Figure 3', 'Figure 3', 1)).toEqual([13, 21]);
    expect(matchOffsets('Figure 3 and Figure 3', 'Figure 3', 2)).toBeNull();
  });
});

describe('buildTextIndex', () => {
  it('flattens text across inline children into one string', () => {
    const root = element('The <strong>quick</strong> <em>brown</em> <a href="https://example.com">fox</a> jumps');
    expect(buildTextIndex(root).text).toBe('The quick brown fox jumps');
  });

  it('collapses whitespace runs to a single space and drops the leading run', () => {
    const root = element('<p>\n   The  \t claim\n\n   is   unproven.  </p>');
    expect(buildTextIndex(root).text).toBe('The claim is unproven.');
  });

  it('points every character at the node it was read from', () => {
    const root = element('The <strong>quick</strong>\n <em>brown</em> fox');
    const { text, sources } = buildTextIndex(root);

    expect(sources).toHaveLength(text.length);
    for (let i = 0; i < text.length; i++) {
      const source = sources[i];
      const char = source.node.nodeValue?.[source.offset];
      // A space is emitted just before the character that ended the run, so
      // both share that character's source; either way the source is the
      // non-space character at or after `i`.
      const expected = text[i] === ' ' ? text[i + 1] : text[i];
      expect(char).toBe(expected);
      expect(char?.trim()).not.toBe('');
    }
  });
});

describe('rangeInElement', () => {
  it('matches a quote that crosses an inline element boundary', () => {
    const root = element('<p>The <strong>quick brown</strong> fox jumps over it.</p>');
    const range = rangeInElement(root, 'quick brown fox');

    expect(range?.toString()).toBe('quick brown fox');
  });

  it('matches the rendered quote across a strong and a link', () => {
    // `display_text` is what the backend's parser made of
    // `**quick** [brown fox](https://example.com)`.
    const root = element('<p>The <strong>quick</strong> <a href="https://example.com">brown fox</a> jumps.</p>');
    const range = rangeInElement(root, 'quick brown fox');

    expect(range?.toString()).toBe('quick brown fox');
  });

  it('returns null when the block does not carry the quote', () => {
    const root = element('<p>The quick brown fox jumps.</p>');

    expect(rangeInElement(root, 'a slow grey badger')).toBeNull();
  });

  it('returns null for an empty quote', () => {
    const root = element('<p>The quick brown fox jumps.</p>');

    expect(rangeInElement(root, '   ')).toBeNull();
  });
});

describe('blocksForLineRange', () => {
  const container = element(`
    <div id="a" data-block-owner="a" data-line-start="1" data-line-end="3">first</div>
    <div id="b" data-block-owner="b" data-line-start="5" data-line-end="7">
      second <span id="nested" data-line-start="6" data-line-end="6">item</span>
    </div>
    <div id="c" data-block-owner="c" data-line-start="10" data-line-end="12">third</div>
    <div id="bad" data-block-owner="bad" data-line-start="oops" data-line-end="nope">broken</div>
  `);

  const ids = (start: number, end: number) => blocksForLineRange(container, start, end).map((block) => block.id);

  it('selects every block overlapping the range, narrowest first', () => {
    expect(ids(6, 11)).toEqual(['nested', 'b', 'c']);
  });

  it('selects a block touching the range at its edge', () => {
    expect(ids(3, 3)).toEqual(['a']);
  });

  it('selects nothing for a range between blocks', () => {
    expect(ids(8, 9)).toEqual([]);
  });

  it('skips non-finite attributes and keeps document order among equal spans', () => {
    expect(ids(1, 100)).toEqual(['nested', 'a', 'b', 'c']);
  });
});

describe('editRanges', () => {
  it('returns a range per findable quote and stops at the first block carrying it', () => {
    const container = element(`
      <div id="first" data-block-owner="first" data-line-start="1" data-line-end="2">
        <p>The claim is <strong>unproven</strong>.</p>
      </div>
      <div id="second" data-block-owner="second" data-line-start="2" data-line-end="3">
        <p>The claim is unproven.</p>
      </div>
    `);

    const ranges = editRanges(container, [
      edit({ id: 'found', display_text: 'The claim is unproven.', start_line: 1, end_line: 3 }),
      edit({ id: 'missing', display_text: 'a sentence the document never had', start_line: 1, end_line: 3 }),
    ]);

    expect(ranges).toHaveLength(1);
    expect(ranges[0].toString()).toBe('The claim is unproven.');
    expect(ranges[0].startContainer.parentElement?.closest('[data-block-owner]')?.id).toBe('first');
  });

  it('prefers the item on the edit line over an identical quote earlier in the same list', () => {
    const container = element(`
      <ul data-block-owner="list" data-line-start="10" data-line-end="12">
        <li id="early" data-line-start="10" data-line-end="10">See Figure 3 for the baseline.</li>
        <li id="middle" data-line-start="11" data-line-end="11">Methods follow.</li>
        <li id="late" data-line-start="12" data-line-end="12">See Figure 3 for the outcome.</li>
      </ul>
    `);

    const ranges = editRanges(container, [edit({ display_text: 'See Figure 3', start_line: 12, end_line: 12 })]);

    expect(ranges).toHaveLength(1);
    expect(ranges[0].startContainer.parentElement?.id).toBe('late');
  });

  it('returns nothing when no block covers the edit lines', () => {
    const container = element('<div data-block-owner="a" data-line-start="1" data-line-end="2">The claim.</div>');

    expect(editRanges(container, [edit({ display_text: 'The claim.', start_line: 40, end_line: 41 })])).toEqual([]);
  });
});

describe('repeated quotes', () => {
  const html =
    '<p data-block-owner="" data-line-start="3" data-line-end="3">Figure 3 and <strong>Figure 3</strong> close the section.</p>';

  it('leaves an ambiguous quote unmarked when no occurrence is given', () => {
    expect(rangeInElement(element(html), 'Figure 3')).toBeNull();
  });

  it('marks the occurrence the edit was anchored to', () => {
    // `**Figure 3**` is unique in the markdown and the second `Figure 3` on
    // the page, which is what the backend stored.
    const [range] = editRanges(element(html), [
      edit({ display_text: 'Figure 3', display_occurrence: 1, start_line: 3, end_line: 3 }),
    ]);

    expect(range.toString()).toBe('Figure 3');
    expect(range.startContainer.parentElement?.tagName).toBe('STRONG');
  });

  it('marks the first occurrence when that is the one stored', () => {
    const [range] = editRanges(element(html), [
      edit({ display_text: 'Figure 3', display_occurrence: 0, start_line: 3, end_line: 3 }),
    ]);

    expect(range.startContainer.parentElement?.tagName).toBe('P');
  });

  it('leaves a repeat inside a block spanning several source lines unmarked', () => {
    // The stored occurrence counted the repeats on line 2 alone, so it says
    // nothing about a block covering lines 1 and 2; marking the wrong half of
    // the paragraph would be worse than marking nothing.
    const wrapped = element(
      '<p data-block-owner="" data-line-start="1" data-line-end="2">See Figure 3 for the baseline. See Figure 3 for the outcome.</p>',
    );

    expect(
      editRanges(wrapped, [edit({ display_text: 'See Figure 3', display_occurrence: 0, start_line: 2, end_line: 2 })]),
    ).toEqual([]);
  });

  it('still marks a quote a multi-line block carries only once', () => {
    const wrapped = element(
      '<p data-block-owner="" data-line-start="1" data-line-end="2">See Figure 3 for the baseline. See Figure 4 for the outcome.</p>',
    );

    const [range] = editRanges(wrapped, [
      edit({ display_text: 'See Figure 4', display_occurrence: 0, start_line: 2, end_line: 2 }),
    ]);

    expect(range.toString()).toBe('See Figure 4');
  });
});

describe('the highlight registry', () => {
  /** Stands in for the browser's `Highlight`, which jsdom does not implement. */
  class FakeHighlight {
    readonly ranges: Range[];

    constructor(...ranges: Range[]) {
      this.ranges = ranges;
    }
  }

  function stubHighlightApi(): Map<string, FakeHighlight> {
    const highlights = new Map<string, FakeHighlight>();
    vi.stubGlobal('CSS', { highlights });
    vi.stubGlobal('Highlight', FakeHighlight);
    return highlights;
  }

  function someRange(): Range {
    const root = element('<p>The claim is unproven.</p>');
    const range = rangeInElement(root, 'The claim');
    if (!range) throw new Error('expected the fixture quote to match');
    return range;
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reports no support under jsdom, where setting and clearing do nothing', () => {
    expect(supportsHighlightApi()).toBe(false);
    expect(() => setEditHighlight([someRange()])).not.toThrow();
    expect(() => clearEditHighlight()).not.toThrow();
  });

  it('files the ranges under the edit highlight name when supported', () => {
    const highlights = stubHighlightApi();
    const range = someRange();

    expect(supportsHighlightApi()).toBe(true);

    setEditHighlight([range]);

    const stored = highlights.get(EDIT_HIGHLIGHT_NAME);
    expect(stored?.ranges).toHaveLength(1);
    expect(stored?.ranges[0]).toBe(range);
  });

  it('adds the style rule to the page once, only when a highlight is painted', () => {
    stubHighlightApi();
    document.getElementById(EDIT_HIGHLIGHT_STYLE_ID)?.remove();

    setEditHighlight([]);
    expect(document.getElementById(EDIT_HIGHLIGHT_STYLE_ID)).toBeNull();

    setEditHighlight([someRange()]);
    setEditHighlight([someRange()]);
    ensureEditHighlightStyle();

    const styles = document.querySelectorAll(`#${EDIT_HIGHLIGHT_STYLE_ID}`);
    expect(styles).toHaveLength(1);
    expect(styles[0].textContent).toContain(`::highlight(${EDIT_HIGHLIGHT_NAME})`);
    expect(styles[0].textContent).toContain('.dark ::highlight');
  });

  it('removes the entry when given no ranges', () => {
    const highlights = stubHighlightApi();
    setEditHighlight([someRange()]);

    setEditHighlight([]);

    expect(highlights.has(EDIT_HIGHLIGHT_NAME)).toBe(false);
  });

  it('removes the entry when cleared', () => {
    const highlights = stubHighlightApi();
    setEditHighlight([someRange()]);

    clearEditHighlight();

    expect(highlights.has(EDIT_HIGHLIGHT_NAME)).toBe(false);
  });
});
