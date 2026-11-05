/** Breathing room between two notes once one has been pushed against another. */
const GAP = 6;

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
 * So the open note, when there is one, is pinned level with its words and
 * the rest are laid out away from it: the notes above are pushed up, the notes
 * below are pushed down. This is what Word and Google Docs do, and it holds
 * however crowded the margin is: when the notes above need more room than the
 * document above the open one offers, the topmost of them are pushed past the
 * top of the margin, out of sight until the note is closed, rather than the
 * open note being pushed down and away from the words it is about.
 */
export function stackNotes(slots: Slot[], pivot: number): number[] {
  const tops = new Array<number>(slots.length);
  if (pivot < 0 || pivot >= slots.length || slots[pivot].wanted === null) {
    stackDown(slots, 0, slots.length, 0, tops);
    return tops;
  }

  const anchorTop = slots[pivot].wanted;
  stackUp(slots, pivot - 1, anchorTop, tops);
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
 * Places slots[..from] bottom to top, none reaching below `ceiling`. A note
 * that does not fit below the top of the margin is placed above it.
 */
function stackUp(slots: Slot[], from: number, ceiling: number, tops: number[]): void {
  let cursor = ceiling;
  for (let index = from; index >= 0; index -= 1) {
    const fits = cursor - slots[index].height - GAP;
    const top = Math.min(slots[index].wanted ?? fits, fits);
    tops[index] = top;
    cursor = top;
  }
}
