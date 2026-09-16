import { IssueEditStatus } from '@/lib/generated-api';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  EDIT_HIGHLIGHT_NAME,
  blocksForLineRange,
  buildTextIndex,
  clearEditHighlight,
  editRanges,
  editSearchText,
  matchOffsets,
  normalizeWhitespace,
  rangeInElement,
  setEditHighlight,
  stripMarkdown,
  supportsHighlightApi,
} from './edit-highlight';
import type { ProposedEdit } from './proposed-edit';

function edit(overrides: Partial<ProposedEdit> = {}): ProposedEdit {
  return {
    id: 'edit-1',
    issue_id: 'issue-1',
    original_text: 'the text',
    replacement_text: 'the better text',
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

describe('stripMarkdown', () => {
  it('drops bold and italic markers', () => {
    expect(stripMarkdown('a **bold** and *slanted* and ***both*** word')).toBe('a bold and slanted and both word');
  });

  it('drops inline code fences and strikethrough', () => {
    expect(stripMarkdown('call `run()` once, ~~twice~~')).toBe('call run() once, twice');
  });

  it('reduces a link to its label', () => {
    expect(stripMarkdown('see [the study](https://example.com/a_b) for more')).toBe('see the study for more');
  });

  it('reduces an image to its alt text', () => {
    expect(stripMarkdown('![Figure 1: yields](https://example.com/f1.png) shows it')).toBe('Figure 1: yields shows it');
  });

  it('drops heading and blockquote prefixes', () => {
    expect(stripMarkdown('## Results\n> quoted line')).toBe('Results\nquoted line');
  });

  it('drops list markers', () => {
    // A `*` bullet loses its asterisk to the emphasis pass first, so the marker
    // regex no longer sees it and the space it sat on survives. Harmless: every
    // caller reads the text through `normalizeWhitespace`.
    expect(stripMarkdown('- first\n+ second\n1. third\n2) fourth')).toBe('first\nsecond\nthird\nfourth');
    expect(stripMarkdown('* starred')).toBe(' starred');
    expect(editSearchText('* starred')).toBe('starred');
  });

  it('keeps snake_case underscores but strips emphasis underscores', () => {
    expect(stripMarkdown('the _stressed_ value of snake_case_name stays')).toBe(
      'the stressed value of snake_case_name stays',
    );
  });
});

describe('normalizeWhitespace', () => {
  it('collapses whitespace runs and trims the edges', () => {
    expect(normalizeWhitespace('  a \n\t b   c  ')).toBe('a b c');
  });
});

describe('editSearchText', () => {
  it('strips markdown and normalizes whitespace together', () => {
    expect(editSearchText('  **The   claim**\n  is [unproven](https://example.com).  ')).toBe('The claim is unproven.');
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

  it('matches a quote still carrying markdown syntax', () => {
    const root = element('<p>The <strong>quick</strong> <a href="https://example.com">brown fox</a> jumps.</p>');
    const range = rangeInElement(root, '**quick** [brown fox](https://example.com)');

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
      second <span id="nested" data-line-start="5" data-line-end="7">item</span>
    </div>
    <div id="c" data-block-owner="c" data-line-start="10" data-line-end="12">third</div>
    <div id="bad" data-block-owner="bad" data-line-start="oops" data-line-end="nope">broken</div>
  `);

  const ids = (start: number, end: number) => blocksForLineRange(container, start, end).map((block) => block.id);

  it('selects every owner block overlapping the range', () => {
    expect(ids(6, 11)).toEqual(['b', 'c']);
  });

  it('selects a block touching the range at its edge', () => {
    expect(ids(3, 3)).toEqual(['a']);
  });

  it('selects nothing for a range between blocks', () => {
    expect(ids(8, 9)).toEqual([]);
  });

  it('skips nested non-owner blocks and non-finite attributes', () => {
    expect(ids(1, 100)).toEqual(['a', 'b', 'c']);
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
      edit({ id: 'found', original_text: 'The claim is **unproven**.', start_line: 1, end_line: 3 }),
      edit({ id: 'missing', original_text: 'a sentence the document never had', start_line: 1, end_line: 3 }),
    ]);

    expect(ranges).toHaveLength(1);
    expect(ranges[0].toString()).toBe('The claim is unproven.');
    expect(ranges[0].startContainer.parentElement?.closest('[data-block-owner]')?.id).toBe('first');
  });

  it('returns nothing when no block covers the edit lines', () => {
    const container = element('<div data-block-owner="a" data-line-start="1" data-line-end="2">The claim.</div>');

    expect(editRanges(container, [edit({ original_text: 'The claim.', start_line: 40, end_line: 41 })])).toEqual([]);
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
