import { describe, expect, it } from 'vitest';
import { diffTokens, type DiffToken, type DiffTokenKind } from './proposed-edit-diff';

const of = (tokens: DiffToken[], kind: DiffTokenKind) => tokens.filter((token) => token.kind === kind);
const joined = (tokens: DiffToken[], kind: DiffTokenKind) =>
  of(tokens, kind)
    .map((token) => token.value)
    .join('');

describe('diffTokens', () => {
  it('surrounds a word swap with the unchanged text', () => {
    const tokens = diffTokens('The quick brown fox', 'The quick grey fox');

    expect(joined(tokens, 'removed')).toContain('brown');
    expect(joined(tokens, 'added')).toContain('grey');
    expect(joined(tokens, 'same')).toContain('The quick');
    expect(joined(tokens, 'same')).toContain('fox');
    expect(tokens.map((token) => token.kind)).toContain('same');
  });

  it('never marks a token both added and removed', () => {
    const tokens = diffTokens('The quick brown fox', 'The quick grey fox');

    expect(tokens.every((token) => ['same', 'added', 'removed'].includes(token.kind))).toBe(true);
    expect(of(tokens, 'removed')).toHaveLength(1);
    expect(of(tokens, 'added')).toHaveLength(1);
  });

  it('reconstructs the original and the replacement from the tokens', () => {
    const tokens = diffTokens('The quick brown fox', 'The quick grey fox');

    expect(
      tokens
        .filter((token) => token.kind !== 'added')
        .map((token) => token.value)
        .join(''),
    ).toBe('The quick brown fox');
    expect(
      tokens
        .filter((token) => token.kind !== 'removed')
        .map((token) => token.value)
        .join(''),
    ).toBe('The quick grey fox');
  });

  it('marks an identical string as unchanged throughout', () => {
    const tokens = diffTokens('The claim is unproven.', 'The claim is unproven.');

    expect(tokens.every((token) => token.kind === 'same')).toBe(true);
    expect(joined(tokens, 'same')).toBe('The claim is unproven.');
  });

  it('treats a whitespace-only difference as no change', () => {
    const tokens = diffTokens('The  claim\n  is   unproven.', 'The claim is unproven.');

    expect(of(tokens, 'removed')).toEqual([]);
    expect(of(tokens, 'added')).toEqual([]);
  });

  it('marks a pure insertion as added only', () => {
    const tokens = diffTokens('The claim is unproven.', 'The claim is likely unproven.');

    expect(of(tokens, 'removed')).toEqual([]);
    expect(joined(tokens, 'added')).toContain('likely');
  });

  it('marks a pure deletion as removed only', () => {
    const tokens = diffTokens('The claim is likely unproven.', 'The claim is unproven.');

    expect(of(tokens, 'added')).toEqual([]);
    expect(joined(tokens, 'removed')).toContain('likely');
  });
});
