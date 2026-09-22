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
  editSearchText,
  matchOffsets,
  normalizeWhitespace,
  rangeInElement,
  setEditHighlight,
  sourceOccurrence,
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
    expect(stripMarkdown('- first\n+ second\n1. third\n2) fourth')).toBe('first\nsecond\nthird\nfourth');
    // The bullet's star is unpaired, so the emphasis pass leaves it for the
    // marker pass, which takes the space with it.
    expect(stripMarkdown('* starred')).toBe('starred');
    expect(editSearchText('* starred')).toBe('starred');
  });

  it('keeps a star that emphasizes nothing', () => {
    expect(stripMarkdown('2 * 3 = 6')).toBe('2 * 3 = 6');
    expect(stripMarkdown('a * b * c')).toBe('a * b * c');
    // A single star between two non-space characters has nothing to close it,
    // so it stays literal.
    expect(stripMarkdown('5*3')).toBe('5*3');
    expect(stripMarkdown('2 ** 3')).toBe('2 ** 3');
  });

  it('drops a star that does emphasize', () => {
    expect(stripMarkdown('**bold**')).toBe('bold');
    expect(stripMarkdown('*it*')).toBe('it');
    expect(stripMarkdown('***both***')).toBe('both');
    expect(stripMarkdown('a * b *c*')).toBe('a * b c');
  });

  it('reads two emphasized words as two', () => {
    expect(stripMarkdown('a *b* and *c* d')).toBe('a b and c d');
    expect(stripMarkdown('a _b_ and _c_ d')).toBe('a b and c d');
  });

  it('keeps snake_case underscores but strips emphasis underscores', () => {
    expect(stripMarkdown('the _stressed_ value of snake_case_name stays')).toBe(
      'the stressed value of snake_case_name stays',
    );
  });

  it('keeps an underscore that emphasizes nothing', () => {
    // No closing partner: an identifier, not emphasis.
    expect(stripMarkdown('_private')).toBe('_private');
    expect(stripMarkdown('foo_')).toBe('foo_');
    expect(stripMarkdown('snake_case_name')).toBe('snake_case_name');
  });

  it('drops an underscore that does emphasize', () => {
    expect(stripMarkdown('_emphasis_')).toBe('emphasis');
    expect(stripMarkdown('__strong__')).toBe('strong');
    expect(stripMarkdown('a _b_ c')).toBe('a b c');
  });

  it('keeps the contents of a code span exactly', () => {
    // The page shows what is between the backticks, syntax and all.
    expect(stripMarkdown('`**name**`')).toBe('**name**');
    expect(stripMarkdown('`a_b`')).toBe('a_b');
    expect(stripMarkdown('`[x](y)`')).toBe('[x](y)');
    expect(stripMarkdown('call `run()` once')).toBe('call run() once');
  });

  it('leaves a backtick with no closing partner alone', () => {
    expect(stripMarkdown('a ` b')).toBe('a ` b');
  });

  it('reduces a link whose label holds brackets, as a DOCX footnote does, to its label', () => {
    expect(stripMarkdown('second cohort [[1]](#footnote-2).')).toBe('second cohort [1].');
    expect(stripMarkdown('see [the [inner] note](http://x) now')).toBe('see the [inner] note now');
    expect(stripMarkdown('![fig [a]](img.png) caption')).toBe('fig [a] caption');
  });

  it('decodes backslash escapes to the character the renderer shows', () => {
    // MarkItDown escapes literal punctuation in DOCX prose; ReactMarkdown
    // renders the bare character, which is what the highlight has to match.
    expect(stripMarkdown('the foo\\_bar variable')).toBe('the foo_bar variable');
    expect(stripMarkdown('a literal \\*star\\* here')).toBe('a literal *star* here');
    expect(stripMarkdown('\\[not a link\\] and 10\\. items')).toBe('[not a link] and 10. items');
    expect(stripMarkdown('C\\# and a\\|b')).toBe('C# and a|b');
  });

  it('does not treat an unescaped backslash before a letter as an escape', () => {
    expect(stripMarkdown('path C:\\Users stays')).toBe('path C:\\Users stays');
  });

  it('keeps a mid-line number that only looks like a list marker', () => {
    expect(stripMarkdown('2019. Annual report', false)).toBe('2019. Annual report');
    expect(stripMarkdown('1. First item')).toBe('First item');
  });

  it('keeps a mid-line hash and arrow, and still strips emphasis', () => {
    expect(stripMarkdown('# 3 of 4', false)).toBe('# 3 of 4');
    expect(stripMarkdown('2019. **Annual** report', false)).toBe('2019. Annual report');
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

  it('passes the line-start flag through to the stripping', () => {
    expect(editSearchText('2019. Annual report', false)).toBe('2019. Annual report');
    expect(editSearchText('2019. Annual report')).toBe('Annual report');
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
      edit({ id: 'found', original_text: 'The claim is **unproven**.', start_line: 1, end_line: 3 }),
      edit({ id: 'missing', original_text: 'a sentence the document never had', start_line: 1, end_line: 3 }),
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

    const ranges = editRanges(container, [edit({ original_text: 'See Figure 3', start_line: 12, end_line: 12 })]);

    expect(ranges).toHaveLength(1);
    expect(ranges[0].startContainer.parentElement?.id).toBe('late');
  });

  it('returns nothing when no block covers the edit lines', () => {
    const container = element('<div data-block-owner="a" data-line-start="1" data-line-end="2">The claim.</div>');

    expect(editRanges(container, [edit({ original_text: 'The claim.', start_line: 40, end_line: 41 })])).toEqual([]);
  });
});

describe('sourceOccurrence', () => {
  const lines = ['# Title', '', 'Figure 3 and **Figure 3** close the section.', 'Again Figure 3 appears here.'];

  it('tells a formatted quote apart from an identical plain one on the same line', () => {
    expect(sourceOccurrence(lines, 3, 3, { original_text: '**Figure 3**', start_line: 3 })).toBe(1);
    expect(sourceOccurrence(lines, 3, 3, { original_text: 'Figure 3 and', start_line: 3 })).toBe(0);
  });

  it('counts occurrences on earlier lines of a block that spans several source lines', () => {
    expect(sourceOccurrence(lines, 3, 4, { original_text: 'Again Figure 3', start_line: 4 })).toBe(0);
    // Unique on its own line, third time the page shows it inside the block.
    expect(sourceOccurrence(lines, 3, 4, { original_text: 'Figure 3', start_line: 4 })).toBe(2);
  });

  it('gives up when the quote is not unique on its line or the line is missing', () => {
    expect(sourceOccurrence(lines, 3, 3, { original_text: 'Figure 3', start_line: 3 })).toBeNull();
    expect(sourceOccurrence(lines, 3, 3, { original_text: 'Figure 3', start_line: 40 })).toBeNull();
  });

  it('matches the quote against the line despite whitespace drift', () => {
    const drifted = ['Energy\u00a0Supply and **Energy Supply** again.'];
    expect(sourceOccurrence(drifted, 1, 1, { original_text: '**Energy Supply**', start_line: 1 })).toBe(1);
  });
});

describe('repeated quotes', () => {
  const html =
    '<p data-block-owner="" data-line-start="3" data-line-end="3">Figure 3 and <strong>Figure 3</strong> close the section.</p>';
  const source = ['# Title', '', 'Figure 3 and **Figure 3** close the section.'];

  it('leaves an ambiguous quote unmarked when no occurrence is known', () => {
    expect(rangeInElement(element(html), '**Figure 3**')).toBeNull();
    expect(editRanges(element(html), [edit({ original_text: '**Figure 3**', start_line: 3, end_line: 3 })])).toEqual(
      [],
    );
  });

  it('marks the occurrence the edit was anchored to when given the source', () => {
    const [range] = editRanges(
      element(html),
      [edit({ original_text: '**Figure 3**', start_line: 3, end_line: 3 })],
      source,
    );

    expect(range.toString()).toBe('Figure 3');
    expect(range.startContainer.parentElement?.tagName).toBe('STRONG');
  });

  it('resolves a repeat on a later source line of a multi-line paragraph', () => {
    const wrapped = element(
      '<p data-block-owner="" data-line-start="1" data-line-end="2">See Figure 3 for the baseline. See Figure 3 for the outcome.</p>',
    );
    const lines = ['See Figure 3 for the baseline.', 'See Figure 3 for the outcome.'];

    const [range] = editRanges(wrapped, [edit({ original_text: 'See Figure 3', start_line: 2, end_line: 2 })], lines);

    expect(range.startOffset).toBe('See Figure 3 for the baseline. '.length);
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
