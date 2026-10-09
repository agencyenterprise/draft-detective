import { HandoffComment, HandoffEdit, ItemOutcome } from '@/lib/generated-api';

/**
 * Where each of a handoff's comments and edits goes, worked out from the paragraphs'
 * text before anything is written.
 *
 * Items are placed by quote because the review was done on an earlier copy of the
 * document: a quote is either still there or it is not, where a paragraph number would
 * silently point somewhere else. A quote found in more than one paragraph is not
 * guessed at either.
 */

export type ParagraphWork = {
  /** Every quote in this group, to find the paragraph again at write time. */
  quotes: string[];
  comments: HandoffComment[];
  edits: HandoffEdit[];
};

export type HandoffPlan = {
  paragraphs: Map<number, ParagraphWork>;
  /** Items that cannot be placed, already reported as not applied. */
  unplaced: ItemOutcome[];
};

export const NOT_FOUND = 'the words are no longer in the document';
export const AMBIGUOUS = 'the words appear in more than one paragraph';

export function normalize(text: string): string {
  return text.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/\s+/g, ' ').trim();
}

/** The one paragraph containing `quote`, or why there is not one. */
export function locate(paragraphs: string[], quote: string): number | typeof NOT_FOUND | typeof AMBIGUOUS {
  const wanted = normalize(quote);
  const hits: number[] = [];
  paragraphs.forEach((text, index) => {
    if (wanted && normalize(text).includes(wanted)) hits.push(index);
  });
  if (hits.length === 0) return NOT_FOUND;
  if (hits.length > 1) return AMBIGUOUS;
  return hits[0];
}

function workFor(plan: HandoffPlan, index: number): ParagraphWork {
  let work = plan.paragraphs.get(index);
  if (!work) {
    work = { quotes: [], comments: [], edits: [] };
    plan.paragraphs.set(index, work);
  }
  return work;
}

export function planHandoff(paragraphs: string[], comments: HandoffComment[], edits: HandoffEdit[]): HandoffPlan {
  const plan: HandoffPlan = { paragraphs: new Map(), unplaced: [] };
  for (const edit of edits) {
    const where = locate(paragraphs, edit.quote);
    if (typeof where !== 'number') {
      plan.unplaced.push({ kind: 'edit', quote: edit.quote, applied: false, detail: where });
      continue;
    }
    const work = workFor(plan, where);
    work.edits.push(edit);
    work.quotes.push(edit.quote);
  }
  for (const comment of comments) {
    const where = locate(paragraphs, comment.quote);
    if (typeof where !== 'number') {
      plan.unplaced.push({ kind: 'comment', quote: comment.quote, applied: false, detail: where });
      continue;
    }
    const work = workFor(plan, where);
    work.comments.push(comment);
    work.quotes.push(comment.quote);
  }
  return plan;
}

/**
 * The paragraph a group belongs to now. Earlier writes can change a paragraph's text
 * (a tracked deletion still reads as text), so it is found again by any of its quotes
 * rather than trusted to keep its position.
 */
export function relocate(paragraphs: string[], work: ParagraphWork): number | null {
  for (const quote of work.quotes) {
    const where = locate(paragraphs, quote);
    if (typeof where === 'number') return where;
  }
  return null;
}
