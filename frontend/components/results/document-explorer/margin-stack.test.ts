import { describe, expect, it } from 'vitest';
import { stackNotes, visualOrder, type Slot } from './margin-stack';

const note = (wanted: number | null, height = 50): Slot => ({ wanted, height });

describe('stackNotes', () => {
  it('stacks top to bottom with nothing open, each at its words unless the one above reaches further', () => {
    expect(stackNotes([note(0), note(20), note(200)], -1)).toEqual([0, 56, 200]);
  });

  it('pins the open note at its words and pushes the notes above it up', () => {
    expect(stackNotes([note(100), note(120), note(130)], 2)).toEqual([18, 74, 130]);
  });

  it('keeps the open note beside its words in a crowded margin, pushing the notes above past the top', () => {
    // Five notes want the top 40px; the open one's words are at 100.
    const slots = [note(0), note(10), note(20), note(30), note(40), note(100)];
    const tops = stackNotes(slots, 5);
    expect(tops[5]).toBe(100);
    expect(tops[0]).toBeLessThan(0);
    // Still in order, none overlapping.
    for (let i = 1; i < tops.length; i++) expect(tops[i]).toBeGreaterThanOrEqual(tops[i - 1] + 50);
  });

  it('pushes the notes below the open one down', () => {
    expect(stackNotes([note(100), note(110)], 0)).toEqual([100, 156]);
  });
});

describe('visualOrder', () => {
  it("orders notes by where they sit, not by their issue's first line", () => {
    // An issue over lines 1-100 with its passage near the bottom, then one on line 50.
    expect(visualOrder([note(900), note(400)])).toEqual([1, 0]);
  });

  it('keeps a note without a position beside its neighbours, and the document group on top', () => {
    expect(visualOrder([note(null), note(300), note(null), note(100)])).toEqual([0, 3, 1, 2]);
  });
});
