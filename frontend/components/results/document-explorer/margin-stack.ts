/** Breathing room between two notes once one has been pushed against another. */
const GAP = 6;

export interface Slot {
  /** The top the note would sit at if nothing else were in the margin, or null for "no preference". */
  wanted: number | null;
  height: number;
}

/**
 * The order the notes are stacked in: top to bottom by where each would like
 * to sit, as measured, not by the line its issue starts on. A note anchored on
 * a passage further down than its issue's first line -- an issue over lines
 * 1-100 with its passage on line 100 -- would otherwise be stacked ahead of
 * the notes it sits below, and push them down after it.
 *
 * A note with no preference keeps its place among its neighbours (it takes
 * the position of the note before it), and one at the very start rides at the
 * top, as the document-level group does. Equal positions keep their order.
 */
export function visualOrder(slots: Slot[]): number[] {
  let previous = Number.NEGATIVE_INFINITY;
  const keys = slots.map((slot) => {
    if (slot.wanted !== null) previous = slot.wanted;
    return previous;
  });
  return slots.map((_, index) => index).sort((a, b) => keys[a] - keys[b]);
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
