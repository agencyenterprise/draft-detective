import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyHandoff, NOT_WRITTEN, outcomesOf, signed } from './apply-handoff';
import { NOT_FOUND, planHandoff, resultsOf } from './handoff-plan';
import { fakeWord } from './word-web-fake';

const PARAGRAPHS = ['Introduction', 'We recieve funding and this is the only option.', 'Funding is discussed below.'];

describe('outcomesOf', () => {
  it('reports each item by its position: written, refused by Word, or not placed', () => {
    const plan = planHandoff(
      PARAGRAPHS,
      [
        { quote: 'the only option', comment: 'Overclaims.' },
        { quote: 'vanished', comment: 'x' },
      ],
      [{ quote: 'recieve', replacement: 'receive' }],
    );

    // The comment at 0 was written; the edit at 2 was found but Word did not write it.
    const items = outcomesOf(plan, new Set([0]), NOT_WRITTEN);

    expect(items.map((item) => [item.index, item.kind, item.applied, item.reason])).toEqual([
      [0, 'comment', true, undefined],
      [1, 'comment', false, 'not_found'],
      [2, 'edit', false, 'refused'],
    ]);
    expect(items[1].detail).toBe(NOT_FOUND);
    expect(items[2].detail).toBe(NOT_WRITTEN);
  });
});

describe('signed', () => {
  it('marks a comment as Draft Detective’s once, even when the agent already did', () => {
    expect(signed('Test comment.')).toBe('Draft Detective: Test comment.');
    expect(signed('Draft Detective: Test comment.')).toBe('Draft Detective: Test comment.');
    expect(signed('draft detective — Test comment.')).toBe('Draft Detective: Test comment.');
  });
});

describe('resultsOf', () => {
  it('reports only positions, outcomes and reason codes', () => {
    expect(
      resultsOf([
        { index: 0, kind: 'comment', quote: 'q', applied: true, detail: '' },
        { index: 1, kind: 'edit', quote: 'q', applied: false, detail: 'free text never sent', reason: 'withheld' },
        { index: 2, kind: 'edit', quote: 'q', applied: false, detail: 'no reason given' },
      ]),
    ).toEqual([
      { index: 0, applied: true, reason: null },
      { index: 1, applied: false, reason: 'withheld' },
      { index: 2, applied: false, reason: 'refused' },
    ]);
  });
});

describe('applyHandoff', () => {
  const PARAGRAPH = 'The structures were developed, for the most part, before a multitude of difficulties arose.';

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /** Apply to a Word for the web that never moves a range, and say what each write landed on. */
  async function apply(
    comments: { quote: string; comment: string }[],
    edits: { quote: string; replacement: string }[],
  ) {
    const fake = fakeWord([PARAGRAPH]);
    vi.stubGlobal('Word', fake.word);
    vi.stubGlobal('Office', fake.office);
    const outcomes = await applyHandoff({ items: { comments, edits } });
    return { outcomes, writes: fake.writes.map(({ kind, words, text }) => [kind, words, text]) };
  }

  it('writes two edits in one paragraph on their own words, the later one first', async () => {
    const { outcomes, writes } = await apply(
      [],
      [
        { quote: 'for the most part', replacement: 'largely' },
        { quote: 'a multitude of difficulties', replacement: 'many difficulties' },
      ],
    );

    expect(outcomes.every((outcome) => outcome.applied)).toBe(true);
    expect(writes).toEqual([
      ['edit', 'a multitude of difficulties', 'many difficulties'],
      ['edit', 'for the most part', 'largely'],
    ]);
  });

  it('puts a comment after an edit in its paragraph on the comment’s own words', async () => {
    const { outcomes, writes } = await apply(
      [{ quote: 'a multitude of difficulties', comment: 'Vague.' }],
      [{ quote: 'for the most part', replacement: 'largely' }],
    );

    expect(outcomes.every((outcome) => outcome.applied)).toBe(true);
    expect(writes).toEqual([
      ['comment', 'a multitude of difficulties', 'Draft Detective: Vague.'],
      ['edit', 'for the most part', 'largely'],
    ]);
  });

  it('keeps a comment on words an edit replaces, or that overlap them', async () => {
    const { writes } = await apply(
      [
        { quote: 'developed, for the most', comment: 'Overlaps.' },
        { quote: 'for the most part', comment: 'Same words.' },
      ],
      [{ quote: 'for the most part', replacement: 'largely' }],
    );

    expect(writes).toEqual([
      ['comment', 'developed, for the most', 'Draft Detective: Overlaps.'],
      ['comment', 'for the most part', 'Draft Detective: Same words.'],
      ['edit', 'for the most part', 'largely'],
    ]);
  });
});
