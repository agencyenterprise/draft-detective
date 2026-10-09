import { describe, expect, it } from 'vitest';
import { AMBIGUOUS, NOT_FOUND, locate, planHandoff, relocate } from './handoff-plan';

const paragraphs = [
  'Introduction',
  'The  results show that   this is the only option.',
  'We recieve funding from two sources.',
  'Funding is discussed below.',
];

describe('locate', () => {
  it('finds a quote whatever its whitespace', () => {
    expect(locate(paragraphs, 'results show that this is')).toBe(1);
  });

  it('treats curly and straight quotes alike', () => {
    expect(locate(["the author's view"], 'the author’s view')).toBe(0);
  });

  it('reports a quote that is gone', () => {
    expect(locate(paragraphs, 'no such words')).toBe(NOT_FOUND);
  });

  it('refuses to choose between two paragraphs', () => {
    expect(locate(paragraphs, 'unding')).toBe(AMBIGUOUS);
  });
});

describe('planHandoff', () => {
  it('groups by paragraph and reports what cannot be placed', () => {
    const plan = planHandoff(
      paragraphs,
      [
        { quote: 'the only option', comment: 'Overclaims.' },
        { quote: 'vanished text', comment: 'x' },
      ],
      [{ quote: 'recieve', replacement: 'receive' }],
    );

    expect([...plan.paragraphs.keys()].sort()).toEqual([1, 2]);
    expect(plan.paragraphs.get(2)?.edits).toHaveLength(1);
    expect(plan.unplaced).toEqual([{ kind: 'comment', quote: 'vanished text', applied: false, detail: NOT_FOUND }]);
  });
});

describe('relocate', () => {
  it('falls back to another quote when the first has been edited away', () => {
    const work = { quotes: ['recieve funding', 'two sources'], comments: [], edits: [] };
    expect(relocate(['Intro', 'We receive funding from two sources.'], work)).toBe(1);
  });
});
