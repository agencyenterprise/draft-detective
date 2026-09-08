/** Breathing room between two notes once one has been pushed against another. */
export const GAP = 6;

export interface Slot {
  /** The top the note would sit at if nothing else were in the margin, or null for "no preference". */
  wanted: number | null;
  height: number;
}

/**
 * Where each note goes, given where it would like to go.
 *
 * With nothing selected the notes are stacked top to bottom: each sits level
 * with its paragraph unless the note above it reaches further down, in which
 * case it is pushed under that note. That alone is not enough. A run of short
 * paragraphs carrying many notes drags the stack past the paragraphs below, so
 * the note the reader just opened lands nowhere near its paragraph.
 *
 * So the open note, when there is one, is pinned level with its paragraph and
 * the rest are laid out away from it: the notes above are pushed up, the notes
 * below are pushed down. This is what Word and Google Docs do. If the notes
 * above the pinned one need more room than the document above it offers, they
 * are stacked down from the top of the margin as they would be with nothing
 * selected, and the open note follows under them — the one case where it
 * cannot sit beside its paragraph.
 */
export function stackNotes(slots: Slot[], pivot: number): number[] {
  const tops = new Array<number>(slots.length);
  if (pivot < 0 || pivot >= slots.length || slots[pivot].wanted === null) {
    stackDown(slots, 0, slots.length, 0, tops);
    return tops;
  }

  let anchorTop = slots[pivot].wanted;
  if (stackUp(slots, pivot - 1, anchorTop, tops)) {
    // The notes above do not fit between the top of the margin and the open
    // note's paragraph, so they are stacked down from the top instead, each at
    // its own paragraph where it can be, and the open note goes under them.
    anchorTop = Math.max(anchorTop, stackDown(slots, 0, pivot, 0, tops));
  }
  tops[pivot] = anchorTop;
  stackDown(slots, pivot + 1, slots.length, anchorTop + slots[pivot].height + GAP, tops);
  return tops;
}

/**
 * Places slots[from..to) top to bottom, none higher than `floor`. Returns the
 * first top free below the last of them.
 */
function stackDown(slots: Slot[], from: number, to: number, floor: number, tops: number[]): number {
  let cursor = floor;
  for (let index = from; index < to; index += 1) {
    const top = Math.max(slots[index].wanted ?? cursor, cursor);
    tops[index] = top;
    cursor = top + slots[index].height + GAP;
  }
  return cursor;
}

/**
 * Places slots[..from] bottom to top, none reaching below `ceiling`. Returns
 * whether the topmost note overshot the top of the margin.
 */
function stackUp(slots: Slot[], from: number, ceiling: number, tops: number[]): boolean {
  let cursor = ceiling;
  for (let index = from; index >= 0; index -= 1) {
    const fits = cursor - slots[index].height - GAP;
    const top = Math.min(slots[index].wanted ?? fits, fits);
    tops[index] = top;
    cursor = top;
  }
  return cursor < 0;
}
